"""Tests for DocumentGenerationService, batch execution, error isolation, and ZIP packaging."""

import io
import os
import zipfile

import pytest
from docx import Document

from apps.data_sources.services import DataSourceService
from apps.documents.models import DocumentType
from apps.generation.models import (
    BatchStatus,
    GenerationDocumentStatus,
)
from apps.generation.services import (
    DocumentGenerationService,
    GenerationValidationError,
)
from apps.mapping.services import MappingService
from apps.templates_manager.models import TemplateStatus
from apps.templates_manager.services import TemplateService
from tests.conftest import make_uploaded_csv, make_uploaded_docx


@pytest.fixture
def generation_fixtures(db, admin_user):
    """Sets up a complete domain graph for document generation tests."""
    doc_type = DocumentType.objects.create(name="Трудовой договор")
    uploaded_docx = make_uploaded_docx(
        filename="contract.docx",
        paragraphs=[
            "Сотрудник {{ employee_name }} принят на должность {{ position }}.",
            "Оклад составляет {{ salary }} руб. Дата документа: {{ current_date }}.",
        ],
    )
    template = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=uploaded_docx,
        name="Трудовой договор v1",
    )

    uploaded_csv = make_uploaded_csv(
        filename="employees.csv",
        rows=[
            ["ФИО", "Должность", "Оклад"],
            ["Иванов Иван", "Инженер", "100000"],
            ["Петров Петр", "Дизайнер", "90000"],
            ["Сидоров Сидор", "Аналитик", "110000"],
        ],
    )
    data_source = DataSourceService.create_data_source(
        name="Штат 2026",
        uploaded_file=uploaded_csv,
        user=admin_user,
    )

    mapping_config = MappingService.create_or_update_mapping_config(
        name="Маппинг трудового договора",
        template=template,
        data_source=data_source,
        rules_data=[
            {"template_variable": "employee_name", "source_column": "ФИО", "required": True},
            {"template_variable": "position", "source_column": "Должность", "required": True},
            {"template_variable": "salary", "source_column": "Оклад", "required": True},
        ],
        user=admin_user,
    )

    return template, data_source, mapping_config


@pytest.mark.django_db
def test_generate_single_document(generation_fixtures, admin_user):
    """Verifies that a single document is successfully generated and filled with values."""
    template, data_source, mapping_config = generation_fixtures
    record = data_source.records.first()

    batch = DocumentGenerationService.create_batch(
        template=template,
        data_source=data_source,
        mapping_config=mapping_config,
        user=admin_user,
        total_records=1,
    )

    doc = DocumentGenerationService.generate_single_document(
        template=template,
        mapping_config=mapping_config,
        data_record=record,
        batch=batch,
    )

    assert doc.status == GenerationDocumentStatus.SUCCESS
    assert doc.file is not None
    assert os.path.exists(doc.file.path)

    # Verify generated DOCX contents
    generated_docx = Document(doc.file.path)
    full_text = " ".join(p.text for p in generated_docx.paragraphs)
    assert "Иванов Иван" in full_text
    assert "Инженер" in full_text
    assert "100000" in full_text
    # System variable resolution check
    assert "{{" not in full_text


@pytest.mark.django_db
def test_generate_batch_and_zip_export(generation_fixtures, admin_user):
    """Verifies full batch document generation and ZIP packaging."""
    _template, data_source, mapping_config = generation_fixtures
    records = list(data_source.records.all())
    assert len(records) == 3

    batch = DocumentGenerationService.generate_batch(
        mapping_config=mapping_config,
        data_records=records,
        user=admin_user,
    )

    assert batch.status == BatchStatus.COMPLETED
    assert batch.total_records == 3
    assert batch.successful_records == 3
    assert batch.failed_records == 0
    assert batch.output_file is not None
    assert os.path.exists(batch.output_file.path)

    # Verify ZIP archive contents
    with zipfile.ZipFile(batch.output_file.path, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 3
        for name in namelist:
            assert name.endswith(".docx")
            doc_bytes = zf.read(name)
            doc_stream = io.BytesIO(doc_bytes)
            read_doc = Document(doc_stream)
            assert len(read_doc.paragraphs) > 0


@pytest.mark.django_db
def test_batch_error_isolation_partial_failure(generation_fixtures, admin_user):
    """Verifies that individual record errors do not crash other records in the batch."""
    _template, data_source, mapping_config = generation_fixtures
    records = list(data_source.records.all())

    # Sabotage record #2 by wiping out required field 'ФИО'
    record_corrupted = records[1]
    record_corrupted.data["ФИО"] = ""
    record_corrupted.save()

    batch = DocumentGenerationService.generate_batch(
        mapping_config=mapping_config,
        data_records=records,
        user=admin_user,
    )

    assert batch.status == BatchStatus.COMPLETED
    assert batch.total_records == 3
    assert batch.successful_records == 2
    assert batch.failed_records == 1

    docs = list(batch.documents.all().order_by("id"))
    assert len(docs) == 3
    assert docs[0].status == GenerationDocumentStatus.SUCCESS
    assert docs[1].status == GenerationDocumentStatus.FAILED
    assert "обязательное поле «employee_name»" in docs[1].error_message
    assert docs[2].status == GenerationDocumentStatus.SUCCESS

    # ZIP archive must contain only the 2 successful documents
    with zipfile.ZipFile(batch.output_file.path, "r") as zf:
        assert len(zf.namelist()) == 2


@pytest.mark.django_db
def test_generate_batch_rejects_inactive_template(generation_fixtures, admin_user):
    """Verifies rejection if template is archived or inactive."""
    template, data_source, mapping_config = generation_fixtures
    template.status = TemplateStatus.ARCHIVED
    template.save()

    records = list(data_source.records.all())
    with pytest.raises(GenerationValidationError) as exc:
        DocumentGenerationService.generate_batch(
            mapping_config=mapping_config,
            data_records=records,
            user=admin_user,
        )
    assert "не активен" in str(exc.value)


@pytest.mark.django_db
def test_generate_batch_rejects_empty_record_selection(generation_fixtures, admin_user):
    """Verifies rejection when no records are passed."""
    _template, _data_source, mapping_config = generation_fixtures
    with pytest.raises(GenerationValidationError) as exc:
        DocumentGenerationService.generate_batch(
            mapping_config=mapping_config,
            data_records=[],
            user=admin_user,
        )
    assert "Не выбрано ни одной записи" in str(exc.value)

"""Tests for domain models across all modules."""

import io

import pytest

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.data_sources.services import DataSourceParserService
from apps.documents.models import DocumentType
from apps.generation.models import BatchStatus, GenerationBatch
from apps.mapping.services import MappingValidationService
from apps.templates_manager.models import DocumentTemplate
from apps.templates_manager.services import TemplateInspectionService


@pytest.mark.django_db
def test_document_type_slug_auto_generation():
    """Verifies slug is automatically populated on DocumentType creation."""
    doc_type = DocumentType.objects.create(name="Labor Agreement 2026")
    assert doc_type.slug == "labor-agreement-2026"


@pytest.mark.django_db
def test_template_inspection_service():
    """Verifies placeholder extraction from Jinja2-style content."""
    template_text = "Agreement between {{ company_name }} and {{ employee_name | upper }} on date {{ signing_date }}."
    variables = TemplateInspectionService.extract_variables_from_text(template_text)
    assert variables == ["company_name", "employee_name", "signing_date"]


def test_data_source_csv_parser():
    """Verifies CSV stream header extraction and row counting."""
    csv_data = "name,role,salary\nAlice,Engineer,5000\nBob,Designer,4500\n"
    stream = io.StringIO(csv_data)
    headers, rows = DataSourceParserService.parse_csv_stream(stream)
    assert headers == ["name", "role", "salary"]
    assert rows == 2


def test_mapping_validation_service():
    """Verifies mapping rule validation logic."""
    variables = ["employee_name", "salary", "bonus"]
    data_columns = ["employee_name", "salary"]
    valid_rules = {
        "employee_name": {"column": "employee_name"},
        "salary": {"column": "salary"},
        "bonus": {"default": "0"},
    }
    is_valid, errors = MappingValidationService.validate_rules(variables, valid_rules, data_columns)
    assert is_valid is True
    assert len(errors) == 0

    # Incomplete rules
    incomplete_rules = {
        "employee_name": {"column": "employee_name"},
    }
    is_valid, errors = MappingValidationService.validate_rules(
        variables, incomplete_rules, data_columns
    )
    assert is_valid is False
    assert len(errors) >= 1


@pytest.mark.django_db
def test_generation_batch_model(standard_user):
    """Verifies generation batch progress and properties."""
    doc_type = DocumentType.objects.create(name="Master Agreement Type")
    template = DocumentTemplate.objects.create(
        document_type=doc_type,
        name="Master Service Agreement",
    )
    batch = GenerationBatch.objects.create(
        template=template,
        initiated_by=standard_user,
        status=BatchStatus.PROCESSING,
        total_records=100,
        processed_records=45,
    )
    assert batch.progress_percent == 45
    assert "Batch #" in str(batch)


@pytest.mark.django_db
def test_audit_logging_service(standard_user):
    """Verifies audit trail creation."""
    AuditService.log(
        action="TEST_ACTION",
        resource_type="DocumentTemplate",
        resource_id="1",
        user=standard_user,
        details={"key": "value"},
    )
    log = AuditLog.objects.first()
    assert log is not None
    assert log.action == "TEST_ACTION"
    assert log.user == standard_user
    assert log.details == {"key": "value"}

"""Tests for document generation views and download endpoints."""

import pytest
from django.urls import reverse

from apps.data_sources.services import DataSourceService
from apps.documents.models import DocumentType
from apps.generation.models import GenerationBatch
from apps.generation.services import DocumentGenerationService
from apps.mapping.services import MappingService
from apps.templates_manager.services import TemplateService
from tests.conftest import make_uploaded_csv, make_uploaded_docx


@pytest.fixture
def batch_fixture(db, admin_user):
    doc_type = DocumentType.objects.create(name="Тип Справки")
    template = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx(
            filename="doc.docx",
            paragraphs=["Привет {{ name }}!"],
        ),
        name="Шаблон справки",
    )
    data_source = DataSourceService.create_data_source(
        name="Пользователи",
        uploaded_file=make_uploaded_csv(
            filename="users.csv",
            rows=[["Имя"], ["Алиса"], ["Боб"]],
        ),
        user=admin_user,
    )
    mapping = MappingService.create_or_update_mapping_config(
        name="Маппинг пользователей",
        template=template,
        data_source=data_source,
        rules_data=[
            {"template_variable": "name", "source_column": "Имя", "required": True},
        ],
        user=admin_user,
    )
    records = list(data_source.records.all())
    batch = DocumentGenerationService.generate_batch(
        mapping_config=mapping,
        data_records=records,
        user=admin_user,
    )
    return mapping, batch


@pytest.mark.django_db
def test_generation_history_view(client, standard_user, batch_fixture):
    """Verifies generation history view for authenticated user."""
    _mapping, batch = batch_fixture
    client.force_login(standard_user)
    res = client.get(reverse("generation:list"))
    assert res.status_code == 200
    assert f"#{batch.id}" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_generation_wizard_view_get_and_post(client, admin_user, batch_fixture):
    """Verifies wizard setup and launching generation via web view."""
    mapping, _batch = batch_fixture
    client.force_login(admin_user)

    wizard_url = reverse("generation:wizard")
    res_get = client.get(f"{wizard_url}?mapping_id={mapping.id}")
    assert res_get.status_code == 200
    assert "Мастер пакетной генерации" in res_get.content.decode("utf-8")

    # POST launch
    records = list(mapping.data_source.records.all())
    res_post = client.post(
        wizard_url,
        {
            "mapping_id": mapping.id,
            "record_ids": [str(r.id) for r in records],
        },
    )
    assert res_post.status_code == 302
    latest_batch = GenerationBatch.objects.order_by("-id").first()
    assert latest_batch.successful_records == 2


@pytest.mark.django_db
def test_generation_detail_view(client, standard_user, batch_fixture):
    """Verifies generation batch detail view with KPI cards and document list."""
    _mapping, batch = batch_fixture
    client.force_login(standard_user)
    res = client.get(reverse("generation:detail", kwargs={"pk": batch.pk}))
    assert res.status_code == 200
    content = res.content.decode("utf-8")
    assert f"Пакет генерации #{batch.id}" in content
    assert "Сформировано успешно" in content


@pytest.mark.django_db
def test_download_batch_zip(client, admin_user, batch_fixture):
    """Verifies downloading the compiled ZIP archive."""
    _mapping, batch = batch_fixture
    client.force_login(admin_user)
    res = client.get(reverse("generation:download_zip", kwargs={"pk": batch.pk}))
    assert res.status_code == 200
    assert "application/zip" in res["Content-Type"] or "octet-stream" in res["Content-Type"]


@pytest.mark.django_db
def test_download_single_docx(client, admin_user, batch_fixture):
    """Verifies downloading an individual generated DOCX file."""
    _mapping, batch = batch_fixture
    client.force_login(admin_user)
    doc = batch.documents.filter(status="SUCCESS").first()
    assert doc is not None

    res = client.get(reverse("generation:download_doc", kwargs={"pk": doc.pk}))
    assert res.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in res["Content-Type"]
        or "octet-stream" in res["Content-Type"]
    )


@pytest.mark.django_db
def test_viewer_cannot_launch_generation(client, viewer_user, batch_fixture):
    """Verifies that VIEWER role receives 403 Forbidden when attempting generation."""
    mapping, _batch = batch_fixture
    client.force_login(viewer_user)

    res_post = client.post(
        reverse("generation:wizard"),
        {
            "mapping_id": mapping.id,
            "select_all": "1",
        },
    )
    assert res_post.status_code == 403

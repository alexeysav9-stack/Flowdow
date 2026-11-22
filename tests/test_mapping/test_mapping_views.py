"""Tests for mapping views and permission enforcement."""

import pytest
from django.urls import reverse

from apps.data_sources.services import DataSourceService
from apps.documents.models import DocumentType
from apps.mapping.models import MappingConfig
from apps.mapping.services import MappingService
from apps.templates_manager.services import TemplateService
from tests.conftest import make_uploaded_csv, make_uploaded_docx


@pytest.fixture
def mapping_setup(db, admin_user):
    doc_type = DocumentType.objects.create(name="Тип Договора")
    template = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx(
            filename="contract.docx",
            paragraphs=["Договор с {{ client_name }} на сумму {{ amount }} руб."],
        ),
        name="Шаблон договора",
    )
    data_source = DataSourceService.create_data_source(
        name="Клиенты",
        uploaded_file=make_uploaded_csv(
            filename="clients.csv",
            rows=[["Клиент", "Сумма"], ["ООО Вектор", "50000"]],
        ),
        user=admin_user,
    )
    mapping = MappingService.create_or_update_mapping_config(
        name="Маппинг клиентов",
        template=template,
        data_source=data_source,
        rules_data=[
            {"template_variable": "client_name", "source_column": "Клиент", "required": True},
            {"template_variable": "amount", "source_column": "Сумма", "required": True},
        ],
        user=admin_user,
    )
    return template, data_source, mapping


@pytest.mark.django_db
def test_mapping_list_view(client, standard_user, mapping_setup):
    """Verifies that authenticated user can view mappings list."""
    _tmpl, _ds, _mapping = mapping_setup
    client.force_login(standard_user)
    res = client.get(reverse("mapping:list"))
    assert res.status_code == 200
    assert "Маппинг клиентов" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_mapping_create_view_get_and_post(client, admin_user, mapping_setup):
    """Verifies creating a mapping via web view."""
    tmpl, ds, _mapping = mapping_setup
    client.force_login(admin_user)

    create_url = reverse("mapping:create")
    # GET with query params
    res_get = client.get(f"{create_url}?template_id={tmpl.id}&data_source_id={ds.id}")
    assert res_get.status_code == 200
    assert "client_name" in res_get.content.decode("utf-8")

    # POST
    res_post = client.post(
        create_url,
        {
            "name": "Новая схема",
            "template": tmpl.id,
            "data_source": ds.id,
            "description": "Описание схемы",
            "col_client_name": "Клиент",
            "req_client_name": "on",
            "col_amount": "Сумма",
            "req_amount": "on",
        },
    )
    assert res_post.status_code == 302
    created = MappingConfig.objects.filter(name="Новая схема").first()
    assert created is not None
    assert created.rules.count() == 2


@pytest.mark.django_db
def test_mapping_detail_view(client, standard_user, mapping_setup):
    """Verifies detail view of a mapping configuration."""
    _tmpl, _ds, mapping = mapping_setup
    client.force_login(standard_user)
    res = client.get(reverse("mapping:detail", kwargs={"pk": mapping.pk}))
    assert res.status_code == 200
    assert "Маппинг клиентов" in res.content.decode("utf-8")
    assert "client_name" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_viewer_cannot_create_or_delete_mapping(client, viewer_user, mapping_setup):
    """Verifies that VIEWER role receives 403 Forbidden for mutating actions."""
    _tmpl, _ds, mapping = mapping_setup
    client.force_login(viewer_user)

    # Attempt create
    res_create = client.get(reverse("mapping:create"))
    assert res_create.status_code == 403

    # Attempt delete
    res_delete = client.post(reverse("mapping:delete", kwargs={"pk": mapping.pk}))
    assert res_delete.status_code == 403
    assert MappingConfig.objects.filter(pk=mapping.pk).exists()

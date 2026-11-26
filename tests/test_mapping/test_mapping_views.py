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
def test_mapping_list_view(client, admin_user, standard_user, mapping_setup):
    """Verifies admin sees org mappings while operator sees only own mappings."""
    _tmpl, _ds, _mapping = mapping_setup
    client.force_login(admin_user)
    res_admin = client.get(reverse("mapping:list"))
    assert res_admin.status_code == 200
    assert "Маппинг клиентов" in res_admin.content.decode("utf-8")

    client.force_login(standard_user)
    res_op = client.get(reverse("mapping:list"))
    assert res_op.status_code == 200
    assert "Маппинг клиентов" not in res_op.content.decode("utf-8")


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
def test_mapping_detail_view(client, admin_user, standard_user, mapping_setup):
    """Verifies detail view for owner/admin and 403 BOLA denial for other operator."""
    _tmpl, _ds, mapping = mapping_setup
    client.force_login(admin_user)
    res = client.get(reverse("mapping:detail", kwargs={"pk": mapping.pk}))
    assert res.status_code == 200
    assert "Маппинг клиентов" in res.content.decode("utf-8")
    assert "client_name" in res.content.decode("utf-8")

    client.force_login(standard_user)
    res_denied = client.get(reverse("mapping:detail", kwargs={"pk": mapping.pk}))
    assert res_denied.status_code == 403


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


@pytest.mark.django_db
def test_mapping_create_view_auto_generates_name_when_empty(client, admin_user, mapping_setup):
    """Verifies that submitting empty name auto-generates a name instead of failing."""
    tmpl, ds, _ = mapping_setup
    client.force_login(admin_user)
    res = client.post(
        reverse("mapping:create"),
        {
            "name": "",
            "template": tmpl.id,
            "data_source": ds.id,
            "col_client_name": "Клиент",
            "req_client_name": "on",
            "col_amount": "Сумма",
            "req_amount": "on",
        },
    )
    assert res.status_code == 302
    created = MappingConfig.objects.filter(data_source=ds, template=tmpl).order_by("-id").first()
    assert created is not None
    assert "Маппинг:" in created.name


@pytest.mark.django_db
def test_mapping_create_view_english_localization(client, admin_user):
    """Verifies mapping create GET prefill and POST auto-name use English in en locale."""
    doc_type = DocumentType.objects.create(name="Contract")
    tmpl = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx(
            filename="contract_en.docx",
            paragraphs=["Contract for {{ client_name }} on {{ current_date }}"],
        ),
        name="Contract Template",
    )
    ds = DataSourceService.create_data_source(
        name="Clients",
        uploaded_file=make_uploaded_csv(
            filename="clients_en.csv",
            rows=[["Client"], ["Acme Corp"]],
        ),
        user=admin_user,
    )

    client.force_login(admin_user)
    client.cookies["django_language"] = "en"

    get_res = client.get(
        f"{reverse('mapping:create')}?template_id={tmpl.id}&data_source_id={ds.id}"
    )
    assert get_res.status_code == 200
    html = get_res.content.decode("utf-8")
    assert "Mapping: Contract — Clients" in html
    assert "Маппинг:" not in html
    assert "System variable — computed automatically" in html
    assert "Системная" not in html

    post_res = client.post(
        reverse("mapping:create"),
        {
            "name": "",
            "template": tmpl.id,
            "data_source": ds.id,
            "col_client_name": "Client",
            "req_client_name": "on",
        },
    )
    assert post_res.status_code == 302
    created = MappingConfig.objects.filter(data_source=ds, template=tmpl).order_by("-id").first()
    assert created is not None
    assert created.name == "Mapping: Contract — Clients"

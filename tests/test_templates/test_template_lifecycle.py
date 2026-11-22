"""Tests for template versioning, lifecycle, activation, and overwriting protection."""

import os

import pytest
from django.urls import reverse

from apps.accounts.models import UserRole
from apps.documents.models import DocumentType
from apps.templates_manager.models import Template, TemplateStatus
from apps.templates_manager.services import TemplateService
from tests.conftest import make_uploaded_docx


@pytest.mark.django_db
def test_create_template_version_1(standard_user):
    """Verifies uploading initial template version (v1) and variable extraction."""
    doc_type = DocumentType.objects.create(name="Трудовой договор")
    file_v1 = make_uploaded_docx(
        filename="contract_v1.docx",
        paragraphs=[
            "Трудовой договор с {{ employee_name }}.",
            "Должность: {{ job_title }}. Оклад: {{ salary }}.",
        ],
    )

    tpl_v1 = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=file_v1,
        name="Трудовой договор v1",
        description="Первая редакция",
        status=TemplateStatus.ACTIVE,
        user=standard_user,
    )

    assert tpl_v1.pk is not None
    assert tpl_v1.version == 1
    assert tpl_v1.status == TemplateStatus.ACTIVE
    assert tpl_v1.detected_variables == ["employee_name", "job_title", "salary"]
    assert doc_type.active_template == tpl_v1
    assert doc_type.total_templates == 1


@pytest.mark.django_db
def test_create_template_version_2_increments_and_preserves_old_file(standard_user):
    """Verifies that uploading a new version auto-increments version number

    and does NOT overwrite or corrupt the previous version's file on disk.
    """
    doc_type = DocumentType.objects.create(name="Акт выполненных работ")

    # Upload v1
    file_v1 = make_uploaded_docx("act.docx", ["Акт #{{ act_num }} на сумму {{ amount }}"])
    tpl_v1 = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=file_v1,
        name="Акт v1",
        status=TemplateStatus.ACTIVE,
        user=standard_user,
    )
    v1_file_path = tpl_v1.file.path
    assert os.path.exists(v1_file_path)
    assert tpl_v1.version == 1

    # Upload v2 with new variables
    file_v2 = make_uploaded_docx(
        "act.docx",
        ["Акт #{{ act_num }} на сумму {{ amount }}, НДС: {{ vat_rate }}"],
    )
    tpl_v2 = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=file_v2,
        name="Акт v2",
        status=TemplateStatus.ACTIVE,
        user=standard_user,
    )
    v2_file_path = tpl_v2.file.path

    # Verify version 2 properties
    assert tpl_v2.version == 2
    assert tpl_v2.status == TemplateStatus.ACTIVE
    assert tpl_v2.detected_variables == ["act_num", "amount", "vat_rate"]

    # Verify v1 was automatically archived
    tpl_v1.refresh_from_db()
    assert tpl_v1.status == TemplateStatus.ARCHIVED

    # Verify distinct files on disk (NO OVERWRITE)
    assert v1_file_path != v2_file_path
    assert os.path.exists(v1_file_path)
    assert os.path.exists(v2_file_path)

    # Active template is now v2
    assert doc_type.active_template == tpl_v2
    assert doc_type.total_templates == 2


@pytest.mark.django_db
def test_activate_and_archive_actions(standard_user):
    """Verifies activating and archiving templates."""
    doc_type = DocumentType.objects.create(name="Дополнительное соглашение")

    tpl_v1 = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx("nda.docx", ["{{ term }}"]),
        status=TemplateStatus.DRAFT,
        user=standard_user,
    )
    tpl_v2 = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx("nda.docx", ["{{ term }}"]),
        status=TemplateStatus.ACTIVE,
        user=standard_user,
    )

    assert tpl_v1.status == TemplateStatus.DRAFT
    assert tpl_v2.status == TemplateStatus.ACTIVE

    # Activate v1 -> v2 should become archived
    TemplateService.activate_template(tpl_v1, user=standard_user)
    tpl_v1.refresh_from_db()
    tpl_v2.refresh_from_db()
    assert tpl_v1.status == TemplateStatus.ACTIVE
    assert tpl_v2.status == TemplateStatus.ARCHIVED

    # Archive v1
    TemplateService.archive_template(tpl_v1, user=standard_user)
    tpl_v1.refresh_from_db()
    assert tpl_v1.status == TemplateStatus.ARCHIVED


@pytest.mark.django_db
def test_template_upload_view(client, standard_user):
    """Verifies template upload via HTTP POST view."""
    doc_type = DocumentType.objects.create(name="Справка")
    client.force_login(standard_user)

    url = reverse("documents:template_upload", kwargs={"pk": doc_type.pk})
    file_obj = make_uploaded_docx(
        "spravka.docx", ["Сотрудник {{ full_name }} работает в отделе {{ department }}"]
    )

    response = client.post(
        url,
        {
            "name": "Справка для визы",
            "file": file_obj,
            "status": "active",
            "description": "Форма справки",
        },
        follow=True,
    )
    assert response.status_code == 200

    tpl = Template.objects.filter(document_type=doc_type).first()
    assert tpl is not None
    assert tpl.name == "Справка для визы"
    assert tpl.version == 1
    assert tpl.detected_variables == ["department", "full_name"]


@pytest.mark.django_db
def test_template_download_view(client, standard_user):
    """Verifies safe downloading of template DOCX file."""
    doc_type = DocumentType.objects.create(name="Договор поставки")
    file_obj = make_uploaded_docx("delivery.docx", ["Поставщик {{ vendor }}"])
    tpl = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=file_obj,
        name="Поставка",
        user=standard_user,
    )

    client.force_login(standard_user)
    url = reverse("templates_manager:download", kwargs={"pk": tpl.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in response["Content-Type"]
    )


@pytest.mark.django_db
def test_viewer_role_cannot_upload_or_activate_templates(client, viewer_user):
    """Verifies that user with VIEWER role cannot upload, activate, or archive templates."""
    doc_type = DocumentType.objects.create(name="Служебная записка")
    file_obj = make_uploaded_docx("memo.docx", ["Записка {{ memo_id }}"])

    client.force_login(viewer_user)
    assert viewer_user.role == UserRole.VIEWER

    # Cannot upload
    upload_url = reverse("documents:template_upload", kwargs={"pk": doc_type.pk})
    upload_res = client.post(upload_url, {"file": file_obj, "name": "Memo", "status": "active"})
    assert upload_res.status_code == 403
    assert Template.objects.filter(document_type=doc_type).count() == 0

    # Create template with service to test activate/archive
    tpl = TemplateService.create_template_version(doc_type, file_obj, status=TemplateStatus.DRAFT)

    # Cannot activate
    act_url = reverse("templates_manager:activate", kwargs={"pk": tpl.pk})
    assert client.post(act_url).status_code == 403

    # Cannot archive
    arch_url = reverse("templates_manager:archive", kwargs={"pk": tpl.pk})
    assert client.post(arch_url).status_code == 403

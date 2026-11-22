"""Tests for Document Types management and permissions."""

import pytest
from django.urls import reverse

from apps.accounts.models import UserRole
from apps.audit.models import AuditLog
from apps.documents.models import DocumentType
from apps.documents.services import DocumentTypeService


@pytest.mark.django_db
def test_create_document_type_service(standard_user):
    """Verifies creating document type via service with audit trail."""
    doc_type = DocumentTypeService.create_document_type(
        name="Трудовой договор 2026",
        description="Стандартный трудовой договор для сотрудников",
        user=standard_user,
    )
    assert doc_type.pk is not None
    assert doc_type.name == "Трудовой договор 2026"
    assert doc_type.slug == "трудовой-договор-2026"
    assert doc_type.total_templates == 0
    assert doc_type.active_template is None

    audit = AuditLog.objects.filter(action="DOCUMENT_TYPE_CREATED").first()
    assert audit is not None
    assert audit.user == standard_user
    assert audit.resource_id == str(doc_type.id)


@pytest.mark.django_db
def test_document_type_list_view(client, standard_user):
    """Verifies document types catalog list view."""
    DocumentType.objects.create(name="Договор подряда")
    DocumentType.objects.create(name="Акт приёма-передачи")

    client.force_login(standard_user)
    response = client.get(reverse("documents:list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Договор подряда" in content
    assert "Акт приёма-передачи" in content


@pytest.mark.django_db
def test_document_type_create_view_success(client, standard_user):
    """Verifies creating document type via POST view."""
    client.force_login(standard_user)
    url = reverse("documents:create")
    response = client.post(
        url,
        {
            "name": "Соглашение о конфиденциальности (NDA)",
            "description": "Защита коммерческой тайны",
        },
        follow=True,
    )
    assert response.status_code == 200
    doc_type = DocumentType.objects.filter(name="Соглашение о конфиденциальности (NDA)").first()
    assert doc_type is not None
    assert doc_type.description == "Защита коммерческой тайны"


@pytest.mark.django_db
def test_document_type_create_duplicate_name(client, standard_user):
    """Verifies duplicate name is rejected with form validation error."""
    DocumentType.objects.create(name="Уникальный договор")
    client.force_login(standard_user)

    url = reverse("documents:create")
    response = client.post(url, {"name": "Уникальный договор"})
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_document_type_detail_view(client, standard_user):
    """Verifies detail view loads and displays document type information."""
    doc_type = DocumentType.objects.create(
        name="Лицензионное соглашение", description="Лицензия ПО"
    )
    client.force_login(standard_user)

    url = reverse("documents:detail", kwargs={"pk": doc_type.pk})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Лицензионное соглашение" in content
    assert "Лицензия ПО" in content


@pytest.mark.django_db
def test_document_type_viewer_cannot_create(client, viewer_user):
    """Verifies user with VIEWER role cannot create document types (403 Forbidden)."""
    client.force_login(viewer_user)
    assert viewer_user.role == UserRole.VIEWER

    url = reverse("documents:create")
    response = client.post(url, {"name": "Запрещенный договор"})
    assert response.status_code == 403
    assert not DocumentType.objects.filter(name="Запрещенный договор").exists()

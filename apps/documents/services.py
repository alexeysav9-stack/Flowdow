"""Service layer for Document Types and Document Taxonomy."""

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit.services import AuditService
from apps.core.permissions import (
    DocumentManagementPermissionMixin,
    can_manage_documents,
    require_permission,
)
from apps.documents.models import DocumentType

__all__ = [
    "DocumentManagementPermissionMixin",
    "DocumentTypeService",
    "can_manage_documents",
]


class DocumentTypeService:
    """Service managing DocumentType taxonomy."""

    @classmethod
    def list_all(cls) -> QuerySet[DocumentType]:
        """Returns all document types with prefetched templates."""
        return DocumentType.objects.prefetch_related("templates").all()

    @classmethod
    def get_by_id(cls, pk: int) -> DocumentType:
        """Retrieves single document type by primary key."""
        return DocumentType.objects.prefetch_related("templates").get(pk=pk)

    @classmethod
    def create_document_type(
        cls,
        name: str,
        description: str = "",
        user: User | None = None,
    ) -> DocumentType:
        """Creates a new document type."""
        if user is not None:
            require_permission(
                can_manage_documents(user),
                _("У вашей роли недостаточно прав для создания типов документов."),
            )
        doc_type = DocumentType.objects.create(
            name=name.strip(),
            description=description.strip(),
        )
        AuditService.log(
            action="DOCUMENT_TYPE_CREATED",
            resource_type="DocumentType",
            resource_id=str(doc_type.id),
            user=user,
            details={"name": doc_type.name},
        )
        return doc_type

    @classmethod
    def update_document_type(
        cls,
        doc_type: DocumentType,
        name: str,
        description: str = "",
        user: User | None = None,
    ) -> DocumentType:
        """Updates document type metadata."""
        if user is not None:
            require_permission(
                can_manage_documents(user),
                _("У вашей роли недостаточно прав для изменения типов документов."),
            )
        doc_type.name = name.strip()
        doc_type.description = description.strip()
        doc_type.save()

        AuditService.log(
            action="DOCUMENT_TYPE_UPDATED",
            resource_type="DocumentType",
            resource_id=str(doc_type.id),
            user=user,
            details={"name": doc_type.name},
        )
        return doc_type

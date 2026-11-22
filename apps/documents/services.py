"""Service layer for Document Types and Document Taxonomy."""

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User, UserRole
from apps.audit.services import AuditService
from apps.documents.models import DocumentType


def can_manage_documents(user: User | None) -> bool:
    """Checks whether the given user has permissions to create or mutate documents and templates.

    Admins, Managers, and Operators have full management permissions.
    Viewers have read-only access.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)


class DocumentManagementPermissionMixin(UserPassesTestMixin):
    """Mixin enforcing document modification rights on views."""

    def test_func(self) -> bool:
        return can_manage_documents(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(
            _(
                "У вашей роли недостаточно прав для создания или изменения шаблонов и типов документов."
            )
        )


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

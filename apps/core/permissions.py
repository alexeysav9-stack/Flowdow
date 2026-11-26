"""Centralized RBAC helpers, object-level access control, and view mixins."""

from collections.abc import Collection
from typing import Any

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import UserRole

ADMIN_ROLES: frozenset[str] = frozenset({UserRole.ADMIN})
MANAGER_OR_ADMIN_ROLES: frozenset[str] = frozenset({UserRole.ADMIN, UserRole.MANAGER})
OPERATIONAL_ROLES: frozenset[str] = frozenset({UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR})


def is_authenticated_active_user(user: Any) -> bool:
    """Returns True when user is an active authenticated account."""
    return bool(
        user and getattr(user, "is_authenticated", False) and getattr(user, "is_active", True)
    )


def has_role(user: Any, allowed_roles: Collection[str]) -> bool:
    """Checks explicit role membership (or superuser), ignoring raw is_staff flag."""
    if not is_authenticated_active_user(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "role", None) in allowed_roles


def is_admin(user: Any) -> bool:
    """Returns True for organization administrators and superusers."""
    return has_role(user, ADMIN_ROLES)


def is_admin_or_manager(user: Any) -> bool:
    """Returns True for ADMIN or MANAGER roles (organization-wide oversight)."""
    return has_role(user, MANAGER_OR_ADMIN_ROLES)


def is_operational_user(user: Any) -> bool:
    """Returns True for ADMIN, MANAGER, or OPERATOR (non-viewer operational roles)."""
    return has_role(user, OPERATIONAL_ROLES)


def can_manage_organization_settings(user: Any) -> bool:
    """Only ADMIN (or superuser) may view or modify organization settings."""
    return is_admin(user)


def can_view_audit_logs(user: Any) -> bool:
    """Only ADMIN and MANAGER may inspect organization audit entries."""
    return is_admin_or_manager(user)


def can_manage_documents(user: Any) -> bool:
    """Checks whether user may create or modify document types and templates."""
    return is_operational_user(user)


def can_download_templates(user: Any) -> bool:
    """Checks whether user may download raw DOCX template files."""
    return is_operational_user(user)


def can_manage_data_sources(user: Any) -> bool:
    """Checks whether user may upload or manage tabular data sources."""
    return is_operational_user(user)


def can_manage_mappings(user: Any) -> bool:
    """Checks whether user may create or manage mapping schemas."""
    return is_operational_user(user)


def can_generate_documents(user: Any) -> bool:
    """Checks whether user may run document generation workflows."""
    return is_operational_user(user)


def can_access_owned_resource(user: Any, owner_id: int | None) -> bool:
    """Enforces organization oversight for ADMIN/MANAGER and strict ownership for OPERATOR.

    VIEWER and unauthenticated users are always denied. Unowned objects (owner_id is None)
    are accessible only to ADMIN and MANAGER.
    """
    if not is_operational_user(user):
        return False
    if is_admin_or_manager(user):
        return True
    return owner_id is not None and owner_id == getattr(user, "id", None)


def can_view_data_source(user: Any, data_source: Any) -> bool:
    """Returns True if user can view or use the given DataSource."""
    return can_access_owned_resource(user, getattr(data_source, "uploaded_by_id", None))


def can_download_data_source(user: Any, data_source: Any) -> bool:
    """Returns True if user can download the raw file of the given DataSource."""
    return can_view_data_source(user, data_source)


def can_delete_data_source(user: Any, data_source: Any) -> bool:
    """Returns True if user can delete the given DataSource."""
    return can_view_data_source(user, data_source)


def can_view_mapping_config(user: Any, mapping_config: Any) -> bool:
    """Returns True if user can view or execute generation with the given MappingConfig."""
    if not can_access_owned_resource(user, getattr(mapping_config, "created_by_id", None)):
        return False
    data_source = getattr(mapping_config, "data_source", None)
    if data_source is not None and not is_admin_or_manager(user):
        return can_view_data_source(user, data_source)
    return True


def can_delete_mapping_config(user: Any, mapping_config: Any) -> bool:
    """Returns True if user can delete the given MappingConfig."""
    return can_access_owned_resource(user, getattr(mapping_config, "created_by_id", None))


def can_view_generation_batch(user: Any, batch: Any) -> bool:
    """Returns True if user can view or download artifacts of the given GenerationBatch."""
    return can_access_owned_resource(user, getattr(batch, "initiated_by_id", None))


def can_download_generated_document(user: Any, document: Any) -> bool:
    """Returns True if user can download an individual GeneratedDocument."""
    batch = getattr(document, "batch", None)
    if batch is None:
        return False
    return can_view_generation_batch(user, batch)


def scope_data_sources(queryset: QuerySet, user: Any) -> QuerySet:
    """Restricts DataSource queryset to records accessible by user."""
    if not is_operational_user(user):
        return queryset.none()
    if is_admin_or_manager(user):
        return queryset
    return queryset.filter(uploaded_by=user)


def scope_mapping_configs(queryset: QuerySet, user: Any) -> QuerySet:
    """Restricts MappingConfig queryset to records accessible by user."""
    if not is_operational_user(user):
        return queryset.none()
    if is_admin_or_manager(user):
        return queryset
    return queryset.filter(created_by=user)


def scope_generation_batches(queryset: QuerySet, user: Any) -> QuerySet:
    """Restricts GenerationBatch queryset to records accessible by user."""
    if not is_operational_user(user):
        return queryset.none()
    if is_admin_or_manager(user):
        return queryset
    return queryset.filter(initiated_by=user)


def require_permission(allowed: bool, message: str) -> None:
    """Raises PermissionDenied with a clear message if allowed is False."""
    if not allowed:
        raise PermissionDenied(message)


def build_user_permissions_context(user: Any) -> dict[str, bool]:
    """Builds permission flags exposed to Django templates via context processor."""
    return {
        "is_admin": is_admin(user),
        "is_admin_or_manager": is_admin_or_manager(user),
        "is_operational": is_operational_user(user),
        "can_manage_settings": can_manage_organization_settings(user),
        "can_view_audit_logs": can_view_audit_logs(user),
        "can_manage_documents": can_manage_documents(user),
        "can_download_templates": can_download_templates(user),
        "can_manage_data_sources": can_manage_data_sources(user),
        "can_manage_mappings": can_manage_mappings(user),
        "can_generate_documents": can_generate_documents(user),
    }


def get_safe_redirect_url(
    request: HttpRequest,
    candidate: str | None,
    fallback: str,
) -> str:
    """Validates a redirect target against the current host to prevent Open Redirect."""
    if not candidate:
        return fallback
    cleaned = candidate.strip()
    if not cleaned or any(ch in cleaned for ch in ("\r", "\n", "\x00")):
        return fallback
    if url_has_allowed_host_and_scheme(
        url=cleaned,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return cleaned
    return fallback


class RoleRequiredMixin(UserPassesTestMixin):
    """Base view mixin enforcing authentication and role authorization."""

    allowed_roles: Collection[str] = ()
    permission_denied_message: str = _(
        "У вашей роли недостаточно прав для выполнения этого действия."
    )

    def test_func(self) -> bool:
        return has_role(self.request.user, self.allowed_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(self.permission_denied_message)


class AdminRequiredMixin(RoleRequiredMixin):
    """View mixin allowing access exclusively to ADMIN users and superusers."""

    allowed_roles = ADMIN_ROLES
    permission_denied_message = _(
        "Доступ к настройкам организации разрешён только администраторам."
    )


class OperationalPermissionMixin(RoleRequiredMixin):
    """View mixin allowing access to operational roles (ADMIN, MANAGER, OPERATOR)."""

    allowed_roles = OPERATIONAL_ROLES


class DocumentManagementPermissionMixin(OperationalPermissionMixin):
    """View mixin enforcing document type and template modification rights."""

    permission_denied_message = _(
        "У вашей роли недостаточно прав для создания или изменения шаблонов и типов документов."
    )


class DataSourcePermissionMixin(OperationalPermissionMixin):
    """View mixin enforcing data source access and modification rights."""

    permission_denied_message = _("У вашей роли недостаточно прав для работы с источниками данных.")


class MappingPermissionMixin(OperationalPermissionMixin):
    """View mixin enforcing mapping schema access and modification rights."""

    permission_denied_message = _(
        "У вашей роли недостаточно прав для работы со схемами сопоставления."
    )


class GenerationPermissionMixin(OperationalPermissionMixin):
    """View mixin enforcing document generation access rights."""

    permission_denied_message = _(
        "У вашей роли недостаточно прав для работы с генерацией документов."
    )

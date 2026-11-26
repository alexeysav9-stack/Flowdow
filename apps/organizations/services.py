"""Organization service layer."""

from typing import Any

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.core.permissions import can_manage_organization_settings, require_permission
from apps.organizations.models import Organization, OrganizationSettings


class OrganizationService:
    """Service managing single-tenant workspace configuration."""

    @classmethod
    def get_or_create_default(cls) -> Organization:
        """Retrieves or provisions the single primary organization and its settings."""
        with transaction.atomic():
            org = Organization.objects.first()
            if not org:
                org = Organization.objects.create(name="Flowdow Workspace")
            if not hasattr(org, "settings"):
                OrganizationSettings.objects.create(organization=org)
            return org

    @classmethod
    def save_settings_forms(
        cls,
        org_form: Any,
        settings_form: Any,
        user: Any | None = None,
    ) -> Organization:
        """Persists validated organization and settings forms with RBAC enforcement."""
        if user is not None:
            require_permission(
                can_manage_organization_settings(user),
                _("Изменять настройки организации может только администратор."),
            )
        with transaction.atomic():
            org = org_form.save()
            settings_form.save()
            return org

    @classmethod
    def update_organization(
        cls,
        org: Organization,
        name: str,
        legal_name: str = "",
        tax_id: str = "",
        email: str = "",
        phone: str = "",
        address: str = "",
        website: str = "",
        user: Any | None = None,
    ) -> Organization:
        if user is not None:
            require_permission(
                can_manage_organization_settings(user),
                _("Изменять настройки организации может только администратор."),
            )
        org.name = name
        org.legal_name = legal_name
        org.tax_id = tax_id
        org.email = email
        org.phone = phone
        org.address = address
        org.website = website
        org.save()
        return org

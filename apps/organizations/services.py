"""Organization service layer."""

from django.db import transaction

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
    ) -> Organization:
        org.name = name
        org.legal_name = legal_name
        org.tax_id = tax_id
        org.email = email
        org.phone = phone
        org.address = address
        org.website = website
        org.save()
        return org

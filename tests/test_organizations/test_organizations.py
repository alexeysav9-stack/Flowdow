"""Tests for organization management and settings."""

import pytest
from django.urls import reverse

from apps.organizations.models import Organization
from apps.organizations.services import OrganizationService


@pytest.mark.django_db
def test_get_or_create_default_organization():
    """Verifies provisioning the single organization and its settings."""
    assert Organization.objects.count() == 0
    org = OrganizationService.get_or_create_default()
    assert org is not None
    assert org.name == "Flowdow Workspace"
    assert hasattr(org, "settings")


@pytest.mark.django_db
def test_organization_settings_view(client, admin_user):
    """Verifies organization settings view loads for ADMIN in Russian and English."""
    client.force_login(admin_user)
    url = reverse("organizations:settings")

    # Russian
    response = client.get(url)
    assert response.status_code == 200
    assert "Настройки организации" in response.content.decode()

    # English
    client.cookies["django_language"] = "en"
    response_en = client.get(url)
    assert response_en.status_code == 200
    assert "Organization Settings" in response_en.content.decode()


@pytest.mark.django_db
def test_organization_settings_denied_for_non_admin_roles(
    client, viewer_user, standard_user, manager_user
):
    """SEC-003: Verifies only ADMIN can view or update organization settings."""
    url = reverse("organizations:settings")
    for role_user in (viewer_user, standard_user, manager_user):
        client.force_login(role_user)
        assert client.get(url).status_code == 403
        assert client.post(url, {"name": "Tampered Corp"}).status_code == 403

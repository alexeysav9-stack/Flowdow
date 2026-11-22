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
def test_organization_settings_view(client, standard_user):
    """Verifies organization settings view loads in Russian and English."""
    client.force_login(standard_user)
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

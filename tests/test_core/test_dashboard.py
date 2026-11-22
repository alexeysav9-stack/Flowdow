"""Tests for core dashboard and health check."""

import pytest
from django.urls import reverse

from apps.core.services import HealthCheckService


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    """Verifies unauthenticated access redirects to login page."""
    url = reverse("core:dashboard")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_dashboard_authenticated(client, standard_user):
    """Verifies authenticated user can view dashboard in Russian and English."""
    client.force_login(standard_user)
    url = reverse("core:dashboard")

    # Default Russian
    response = client.get(url)
    assert response.status_code == 200
    assert "Панель управления" in response.content.decode()

    # English switch
    client.cookies["django_language"] = "en"
    response_en = client.get(url)
    assert response_en.status_code == 200
    assert "Dashboard" in response_en.content.decode()


@pytest.mark.django_db
def test_health_check_endpoint(client):
    """Verifies health check endpoint returns 200 and valid JSON."""
    url = reverse("core:health")
    response = client.get(url)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "database" in data


def test_health_check_service():
    """Unit test for health check service."""
    report = HealthCheckService.check_health()
    assert isinstance(report, dict)
    assert "status" in report
    assert "database" in report

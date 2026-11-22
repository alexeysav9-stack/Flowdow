"""Tests for authentication views and profile management."""

import pytest
from django.urls import reverse

from apps.accounts.services import UserService


@pytest.mark.django_db
def test_login_view_get(client):
    """Verifies login page loads successfully in Russian (default) and English."""
    url = reverse("accounts:login")

    # Default Russian locale
    response = client.get(url)
    assert response.status_code == 200
    assert "Вход в Flowdow" in response.content.decode()

    # English locale via cookie
    client.cookies["django_language"] = "en"
    response_en = client.get(url)
    assert response_en.status_code == 200
    assert "Sign in to Flowdow" in response_en.content.decode()


@pytest.mark.django_db
def test_login_successful(client, standard_user):
    """Verifies valid credentials log the user in and redirect to dashboard."""
    url = reverse("accounts:login")
    response = client.post(
        url,
        {"username": "testuser", "password": "testpassword123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["user"].is_authenticated


@pytest.mark.django_db
def test_logout_view(client, standard_user):
    """Verifies logout terminates user session."""
    client.force_login(standard_user)
    url = reverse("accounts:logout")
    response = client.post(url, follow=True)
    assert response.status_code == 200
    assert not response.context["user"].is_authenticated


@pytest.mark.django_db
def test_profile_update_service(standard_user):
    """Verifies updating user profile via UserService."""
    updated = UserService.update_profile(
        user=standard_user,
        first_name="Alice Updated",
        job_title="Lead Operator",
        phone="+999999999",
    )
    assert updated.first_name == "Alice Updated"
    assert updated.job_title == "Lead Operator"
    assert updated.phone == "+999999999"

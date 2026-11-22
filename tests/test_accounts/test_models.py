"""Tests for custom User model."""

import pytest

from apps.accounts.models import User, UserRole


@pytest.mark.django_db
def test_create_custom_user():
    """Verifies creating custom user with roles and profile fields."""
    user = User.objects.create_user(
        username="counsel",
        email="counsel@flowdow.local",
        password="secretpassword",
        role=UserRole.MANAGER,
        job_title="Senior Legal Counsel",
        phone="+1234567890",
    )
    assert user.username == "counsel"
    assert user.role == UserRole.MANAGER
    assert user.job_title == "Senior Legal Counsel"
    assert user.phone == "+1234567890"
    assert not user.is_admin_role


@pytest.mark.django_db
def test_admin_user_role():
    """Verifies is_admin_role property on admin user."""
    admin = User.objects.create_superuser(
        username="root",
        email="root@flowdow.local",
        password="rootpassword",
        role=UserRole.ADMIN,
    )
    assert admin.is_admin_role
    assert admin.is_superuser

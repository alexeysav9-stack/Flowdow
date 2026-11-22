"""Accounts business logic and service layer."""

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import User, UserRole

UserModel = get_user_model()


class UserService:
    """Service handling user creation, updates, and role validation."""

    @classmethod
    def create_user(
        cls,
        username: str,
        email: str,
        password: str,
        role: str = UserRole.OPERATOR,
        first_name: str = "",
        last_name: str = "",
        job_title: str = "",
        is_staff: bool = False,
    ) -> User:
        """Creates a new user record with encrypted password."""
        with transaction.atomic():
            user = UserModel.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                first_name=first_name,
                last_name=last_name,
                job_title=job_title,
                is_staff=is_staff,
            )
            return user

    @classmethod
    def update_profile(
        cls,
        user: User,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        job_title: str | None = None,
        phone: str | None = None,
    ) -> User:
        """Updates user profile details."""
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None:
            user.email = email
        if job_title is not None:
            user.job_title = job_title
        if phone is not None:
            user.phone = phone
        user.save()
        return user

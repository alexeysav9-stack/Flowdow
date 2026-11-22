"""Custom User model for Flowdow."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", _("Администратор")
    MANAGER = "MANAGER", _("Менеджер")
    OPERATOR = "OPERATOR", _("Оператор")
    VIEWER = "VIEWER", _("Наблюдатель")


class User(AbstractUser):
    """Custom user model extending AbstractUser.

    Configured prior to initial database migrations to guarantee future
    schema stability and seamless extensibility.
    """

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.OPERATOR,
        verbose_name="System Role",
        help_text="Role determining default capabilities within Flowdow.",
    )
    job_title = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="Job Title",
        help_text="Professional title or designation (e.g. Legal Counsel, HR Specialist).",
    )
    phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name="Phone Number",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]

    def __str__(self) -> str:
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.username})"
        return self.username

    @property
    def is_admin_role(self) -> bool:
        """Returns True if user has the ADMIN role or superuser rights."""
        return self.role == UserRole.ADMIN or self.is_superuser

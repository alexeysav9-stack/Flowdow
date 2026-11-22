"""Organization models for single-tenant workspace settings."""

from django.db import models

from apps.core.models import TimeStampedModel


class Organization(TimeStampedModel):
    """Represents the host organization / company operating this Flowdow instance."""

    name = models.CharField(
        max_length=150,
        default="My Organization",
        verbose_name="Organization Name",
    )
    legal_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Legal Entity Name",
    )
    tax_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Tax ID / Registration Number",
    )
    email = models.EmailField(
        blank=True,
        default="",
        verbose_name="Contact Email",
    )
    phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name="Contact Phone",
    )
    address = models.TextField(
        blank=True,
        default="",
        verbose_name="Office Address",
    )
    website = models.URLField(
        blank=True,
        default="",
        verbose_name="Website",
    )

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self) -> str:
        return self.name


class OrganizationSettings(TimeStampedModel):
    """Default preferences and formatting rules for the organization."""

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name="Organization",
    )
    default_date_format = models.CharField(
        max_length=32,
        default="DD.MM.YYYY",
        verbose_name="Default Date Format",
        help_text="Standard date formatting for generated documents.",
    )
    default_currency = models.CharField(
        max_length=8,
        default="USD",
        verbose_name="Default Currency",
    )
    retention_days = models.PositiveIntegerField(
        default=90,
        verbose_name="File Retention Period (Days)",
        help_text="Number of days to preserve generated batches in storage.",
    )

    class Meta:
        verbose_name = "Organization Settings"
        verbose_name_plural = "Organization Settings"

    def __str__(self) -> str:
        return f"Settings for {self.organization.name}"

"""Models for document classification."""

import uuid

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class DocumentType(TimeStampedModel):
    """Categorizes documents (e.g. Employment Contract, NDA, Service Agreement)."""

    name = models.CharField(
        max_length=120,
        unique=True,
        verbose_name="Document Type Name",
    )
    slug = models.SlugField(
        max_length=140,
        unique=True,
        blank=True,
        verbose_name="Identifier Slug",
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Description",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
    )

    class Meta:
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            generated = slugify(self.name, allow_unicode=True)
            self.slug = generated if generated else f"type-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    @property
    def active_template(self):
        """Returns the currently active template for this document type, if any."""
        return self.templates.filter(status="active").order_by("-version").first()

    @property
    def total_templates(self) -> int:
        """Returns the total number of template versions."""
        return self.templates.count()

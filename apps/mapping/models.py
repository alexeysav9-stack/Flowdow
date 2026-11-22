"""Models for variable-to-column field mapping."""

from django.db import models

from apps.core.models import TimeStampedModel
from apps.data_sources.models import DataSource
from apps.templates_manager.models import DocumentTemplate


class FieldMappingSchema(TimeStampedModel):
    """Configuration mapping template variables to tabular columns."""

    name = models.CharField(
        max_length=150,
        verbose_name="Mapping Name",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="mappings",
        verbose_name="Template",
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mappings",
        verbose_name="Default Data Source",
    )
    rules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Mapping Rules",
        help_text="Key-value mapping from template placeholder to dataset column, defaults, and formats.",
    )

    class Meta:
        verbose_name = "Field Mapping Schema"
        verbose_name_plural = "Field Mapping Schemas"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.template.title})"

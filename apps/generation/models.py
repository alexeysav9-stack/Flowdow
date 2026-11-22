"""Models for document generation batches and records."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.data_sources.models import DataSource
from apps.templates_manager.models import DocumentTemplate


class BatchStatus(models.TextChoices):
    PENDING = "PENDING", _("В очереди")
    PROCESSING = "PROCESSING", _("Обработка")
    COMPLETED = "COMPLETED", _("Завершено")
    FAILED = "FAILED", _("Ошибка")


class GenerationBatch(TimeStampedModel):
    """Represents a single document generation run or batch export."""

    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name="Template",
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
        verbose_name="Data Source",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_batches",
        verbose_name="Initiated By",
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name="Status",
    )
    total_records = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Records",
    )
    processed_records = models.PositiveIntegerField(
        default=0,
        verbose_name="Processed Records",
    )
    output_file = models.FileField(
        upload_to="output/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Output Archive / Document",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name="Error Diagnostics",
    )

    class Meta:
        verbose_name = "Generation Batch"
        verbose_name_plural = "Generation Batches"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Batch #{self.id} — {self.template.title} [{self.status}]"

    @property
    def progress_percent(self) -> int:
        if self.total_records == 0:
            return 100 if self.status == BatchStatus.COMPLETED else 0
        return int((self.processed_records / self.total_records) * 100)

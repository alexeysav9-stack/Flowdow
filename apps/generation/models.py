"""Models for document generation batches and individual generated documents."""

import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.data_sources.models import DataRecord, DataSource
from apps.mapping.models import MappingConfig
from apps.templates_manager.models import Template


def batch_output_path(instance: "GenerationBatch", filename: str) -> str:
    """Generates path for the batch archive."""
    ext = os.path.splitext(filename)[1].lower() or ".zip"
    timestamp = timezone.now().strftime("%Y%m")
    token = uuid.uuid4().hex[:8]
    return f"output/batches/{timestamp}/batch_{instance.pk or 'new'}_{token}{ext}"


def generated_document_path(instance: "GeneratedDocument", filename: str) -> str:
    """Generates path for an individual DOCX document."""
    ext = os.path.splitext(filename)[1].lower() or ".docx"
    timestamp = timezone.now().strftime("%Y%m")
    token = uuid.uuid4().hex[:8]
    return f"output/documents/{timestamp}/doc_{instance.batch_id or 'b'}_{token}{ext}"


class BatchStatus(models.TextChoices):
    PENDING = "PENDING", _("В очереди")
    PROCESSING = "PROCESSING", _("Обработка")
    COMPLETED = "COMPLETED", _("Завершено")
    FAILED = "FAILED", _("Ошибка")


class GenerationDocumentStatus(models.TextChoices):
    SUCCESS = "SUCCESS", _("Успешно")
    FAILED = "FAILED", _("Ошибка")


class GenerationBatch(TimeStampedModel):
    """Represents a single document generation batch run."""

    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name=_("Шаблон документа"),
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
        verbose_name=_("Источник данных"),
    )
    mapping_config = models.ForeignKey(
        MappingConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
        verbose_name=_("Схема маппинга"),
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_batches",
        verbose_name=_("Инициатор"),
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name=_("Статус"),
    )
    total_records = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Всего записей"),
    )
    processed_records = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Обработано записей"),
    )
    successful_records = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Успешно сформировано"),
    )
    failed_records = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ошибок при формировании"),
    )
    output_file = models.FileField(
        upload_to=batch_output_path,
        blank=True,
        null=True,
        verbose_name=_("Архив пакета (ZIP)"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Диагностика ошибок"),
    )

    class Meta:
        verbose_name = _("Пакет генерации")
        verbose_name_plural = _("Пакеты генерации")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Batch #{self.id} — {self.template.name} [{self.status}]"

    @property
    def progress_percent(self) -> int:
        if self.total_records == 0:
            return 100 if self.status == BatchStatus.COMPLETED else 0
        return int((self.processed_records / self.total_records) * 100)


class GeneratedDocument(TimeStampedModel):
    """Individual document produced during a batch run."""

    batch = models.ForeignKey(
        GenerationBatch,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Пакет генерации"),
    )
    data_record = models.ForeignKey(
        DataRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_documents",
        verbose_name=_("Запись данных"),
    )
    file = models.FileField(
        upload_to=generated_document_path,
        blank=True,
        null=True,
        verbose_name=_("Файл документа (DOCX)"),
    )
    status = models.CharField(
        max_length=20,
        choices=GenerationDocumentStatus.choices,
        default=GenerationDocumentStatus.SUCCESS,
        verbose_name=_("Статус генерации"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Сообщение об ошибке"),
    )
    record_identifier = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Идентификатор записи"),
    )

    class Meta:
        verbose_name = _("Сформированный документ")
        verbose_name_plural = _("Сформированные документы")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Doc #{self.id} (Batch #{self.batch_id}) [{self.status}]"

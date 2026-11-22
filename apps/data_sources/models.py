"""Models for managing imported tabular datasets and extracted records."""

import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


def data_source_upload_path(instance: "DataSource", filename: str) -> str:
    """Generates a secure, collision-free storage path for data files."""
    ext = os.path.splitext(filename)[1].lower()
    clean_name = slugify(instance.name, allow_unicode=True) or "dataset"
    token = uuid.uuid4().hex[:10]
    timestamp = timezone.now().strftime("%Y%m")
    return f"data_sources/{timestamp}/{token}_{clean_name}{ext}"


class DataSourceFormat(models.TextChoices):
    CSV = "csv", _("Значения через запятую (CSV)")
    XLSX = "xlsx", _("Электронная таблица Excel (XLSX)")


# Backward compatibility alias
FileFormat = DataSourceFormat


class DataSourceStatus(models.TextChoices):
    PENDING = "pending", _("В ожидании")
    PROCESSING = "processing", _("Обработка")
    READY = "ready", _("Готов")
    ERROR = "error", _("Ошибка")


class DataSource(TimeStampedModel):
    """Represents an uploaded CSV or XLSX dataset used as generation inputs."""

    name = models.CharField(
        max_length=200,
        verbose_name=_("Наименование набора данных"),
    )
    file = models.FileField(
        upload_to=data_source_upload_path,
        verbose_name=_("Файл данных"),
    )
    format = models.CharField(
        max_length=10,
        choices=DataSourceFormat.choices,
        default=DataSourceFormat.CSV,
        verbose_name=_("Формат файла"),
    )
    status = models.CharField(
        max_length=20,
        choices=DataSourceStatus.choices,
        default=DataSourceStatus.PENDING,
        verbose_name=_("Статус обработки"),
    )
    sheet_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name=_("Имя листа таблицы"),
        help_text=_("Имя листа для файлов Excel (XLSX)."),
    )
    headers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Заголовки колонок"),
        help_text=_("Список извлеченных заголовков колонок."),
    )
    row_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Количество строк"),
        help_text=_("Общее количество строк данных (без заголовка)."),
    )
    column_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Количество колонок"),
        help_text=_("Количество валидных распознанных колонок."),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Описание"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Диагностика ошибок"),
        help_text=_("Сообщение об ошибке, если импорт завершился со сбоем."),
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_data_sources",
        verbose_name=_("Кем загружен"),
    )

    class Meta:
        verbose_name = _("Источник данных")
        verbose_name_plural = _("Источники данных")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.format.upper()}, {self.row_count} строк)"

    # Backwards compatibility properties
    @property
    def file_format(self) -> str:
        return self.format.upper()

    @file_format.setter
    def file_format(self, value: str) -> None:
        self.format = str(value).lower()

    @property
    def detected_columns(self) -> list[str]:
        return self.headers

    @detected_columns.setter
    def detected_columns(self, value: list[str]) -> None:
        self.headers = value


class DataRecord(TimeStampedModel):
    """Dynamic tabular record extracted from a DataSource."""

    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name=_("Источник данных"),
    )
    row_number = models.PositiveIntegerField(
        verbose_name=_("Номер строки"),
        help_text=_("Порядковый номер строки в исходном файле (1-based, без заголовка)."),
    )
    data = models.JSONField(
        default=dict,
        verbose_name=_("Данные строки"),
        help_text=_("Динамический словарь {имя_колонки: значение}."),
    )

    class Meta:
        verbose_name = _("Запись данных")
        verbose_name_plural = _("Записи данных")
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "row_number"],
                name="unique_datasource_record_row",
            )
        ]
        indexes = [
            models.Index(fields=["data_source", "row_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.data_source.name} [#{self.row_number}]"

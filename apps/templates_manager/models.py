"""Models for managing DOCX templates and their versioned revisions."""

import os
import uuid

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.documents.models import DocumentType


def template_upload_path(instance: "Template", filename: str) -> str:
    """Generates a secure, collision-free storage path for uploaded DOCX templates.

    Structure: templates/<document_type_id>/v<version>_<token>_<slug>.docx
    Prevents path traversal and protects older versions from accidental overwriting.
    """
    clean_name = os.path.basename(filename)
    root, _ext = os.path.splitext(clean_name)
    sanitized_slug = slugify(root) or "template"
    unique_token = uuid.uuid4().hex[:8]
    doc_type_id = instance.document_type_id or "unassigned"
    version_label = f"v{instance.version or 1}"
    safe_filename = f"{version_label}_{unique_token}_{sanitized_slug}.docx"
    return os.path.join("templates", str(doc_type_id), safe_filename)


class TemplateStatus(models.TextChoices):
    DRAFT = "draft", _("Черновик")
    ACTIVE = "active", _("Активен")
    ARCHIVED = "archived", _("В архиве")


class Template(TimeStampedModel):
    """Represents a versioned DOCX template tied to a specific DocumentType."""

    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.CASCADE,
        related_name="templates",
        verbose_name=_("Тип документа"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Название шаблона"),
        help_text=_("Понятное наименование шаблона (например, Стандартный договор 2026)."),
    )
    file = models.FileField(
        upload_to=template_upload_path,
        verbose_name=_("DOCX файл"),
        help_text=_("Файл шаблона в формате DOCX с Jinja2-переменными."),
    )
    version = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Версия"),
        help_text=_("Порядковый номер версии шаблона."),
    )
    status = models.CharField(
        max_length=20,
        choices=TemplateStatus.choices,
        default=TemplateStatus.ACTIVE,
        verbose_name=_("Статус"),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Описание"),
    )
    detected_variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Обнаруженные переменные"),
        help_text=_("Список плейсхолдеров, извлечённых из шаблона."),
    )

    class Meta:
        verbose_name = _("Шаблон документа")
        verbose_name_plural = _("Шаблоны документов")
        ordering = ["document_type", "-version", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "version"],
                name="unique_template_document_type_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_type.name} — {self.name} (v{self.version}) [{self.get_status_display()}]"

    # Backward-compatibility aliases for DocumentTemplate
    @property
    def title(self) -> str:
        return self.name

    @title.setter
    def title(self, value: str) -> None:
        self.name = value

    @property
    def is_active(self) -> bool:
        return self.status == TemplateStatus.ACTIVE


# Alias for backward compatibility with existing apps
DocumentTemplate = Template

"""Models for template-to-datasource variable mapping."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.data_sources.models import DataSource
from apps.templates_manager.models import Template


class MappingConfig(TimeStampedModel):
    """Configuration binding template variables to tabular data source columns."""

    name = models.CharField(
        max_length=200,
        verbose_name=_("Название схемы маппинга"),
        help_text=_("Понятное наименование конфигурации (например, Ведомость 2026)."),
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="mapping_configs",
        verbose_name=_("Шаблон документа"),
    )
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="mapping_configs",
        verbose_name=_("Источник данных"),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Описание"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_mappings",
        verbose_name=_("Создал"),
    )

    class Meta:
        verbose_name = _("Конфигурация маппинга")
        verbose_name_plural = _("Конфигурации маппинга")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.template.name} → {self.data_source.name})"

    @property
    def total_rules(self) -> int:
        return self.rules.count()

    def get_rules_dict(self) -> dict[str, dict[str, Any]]:
        """Returns dictionary of rules for fast context construction and validation."""
        result = {}
        for rule in self.rules.all():
            result[rule.template_variable] = {
                "source_column": rule.source_column,
                "default_value": rule.default_value,
                "required": rule.required,
            }
        return result

    def as_rules_dict(self) -> dict[str, dict[str, Any]]:
        """Alias for get_rules_dict."""
        return self.get_rules_dict()


class MappingRule(TimeStampedModel):
    """Specific variable-to-column mapping rule inside a MappingConfig."""

    mapping_config = models.ForeignKey(
        MappingConfig,
        on_delete=models.CASCADE,
        related_name="rules",
        verbose_name=_("Конфигурация маппинга"),
    )
    template_variable = models.CharField(
        max_length=150,
        verbose_name=_("Переменная шаблона"),
        help_text=_("Имя плейсхолдера в DOCX (например, full_name, specialty)."),
    )
    source_column = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Колонка источника"),
        help_text=_("Название колонки в таблице данных."),
    )
    default_value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Значение по умолчанию"),
        help_text=_("Подставляется, если значение в таблице пустое."),
    )
    required = models.BooleanField(
        default=True,
        verbose_name=_("Обязательное поле"),
        help_text=_("Если True, значение переменной не должно оставаться пустым при генерации."),
    )

    class Meta:
        verbose_name = _("Правило сопоставления")
        verbose_name_plural = _("Правила сопоставления")
        ordering = ["template_variable"]
        constraints = [
            models.UniqueConstraint(
                fields=["mapping_config", "template_variable"],
                name="unique_mapping_config_variable",
            )
        ]

    def __str__(self) -> str:
        target = self.source_column or f"Default: '{self.default_value}'"
        return f"{self.template_variable} → {target}"


# Backward compatibility alias
FieldMappingSchema = MappingConfig

"""Forms for mapping configuration."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.data_sources.models import DataSource, DataSourceStatus
from apps.mapping.models import MappingConfig
from apps.templates_manager.models import Template, TemplateStatus


class MappingConfigForm(forms.ModelForm):
    """Form for creating or editing the top-level MappingConfig entity."""

    template = forms.ModelChoiceField(
        queryset=Template.objects.filter(status=TemplateStatus.ACTIVE).select_related(
            "document_type"
        ),
        label=_("Активный шаблон"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Отображаются только активные версии шаблонов."),
    )
    data_source = forms.ModelChoiceField(
        queryset=DataSource.objects.filter(status=DataSourceStatus.READY),
        label=_("Источник данных"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Отображаются только готовые наборы данных (CSV / XLSX)."),
    )

    class Meta:
        model = MappingConfig
        fields = ["name", "template", "data_source", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Например: Маппинг договора подряда 2026"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Необязательное описание схемы сопоставления..."),
                }
            ),
        }


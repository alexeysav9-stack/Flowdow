"""Forms for mapping configuration."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.data_sources.models import DataSource, DataSourceStatus
from apps.mapping.models import MappingConfig
from apps.templates_manager.models import Template, TemplateStatus


class MappingConfigForm(forms.ModelForm):
    """Form for creating or editing the top-level MappingConfig entity."""

    name = forms.CharField(
        max_length=200,
        required=False,
        label=_("Название схемы маппинга"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Например: Маппинг договора подряда 2026"),
            }
        ),
        help_text=_("Если не заполнено, будет сформировано автоматически."),
    )

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
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Необязательное описание схемы сопоставления..."),
                }
            ),
        }

    def clean(self) -> dict:
        cleaned_data = super().clean()
        name = (cleaned_data.get("name") or "").strip()
        template = cleaned_data.get("template")
        data_source = cleaned_data.get("data_source")

        if not name:
            if template and data_source:
                doc_type_name = getattr(
                    getattr(template, "document_type", None), "name", template.name
                )
                cleaned_data["name"] = str(
                    _("Маппинг: %(doc_type)s — %(data_source)s")
                    % {
                        "doc_type": doc_type_name,
                        "data_source": data_source.name,
                    }
                )
            else:
                self.add_error("name", _("Укажите наименование схемы сопоставления."))
        else:
            cleaned_data["name"] = name

        return cleaned_data

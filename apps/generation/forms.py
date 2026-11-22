"""Forms for document generation batches."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.mapping.models import MappingConfig


class BatchLaunchForm(forms.Form):
    """Form for selecting mapping and initiating batch generation."""

    mapping_config = forms.ModelChoiceField(
        queryset=MappingConfig.objects.select_related("template", "data_source"),
        label=_("Схема сопоставления (Mapping)"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Выберите конфигурацию сопоставления шаблона и источника данных."),
    )


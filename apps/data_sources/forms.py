"""Forms for uploading and configuring data sources."""

import os

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.data_sources.services import DataSourceSecurityValidator


class DataSourceUploadForm(forms.Form):
    """Form for uploading CSV and XLSX datasets."""

    name = forms.CharField(
        max_length=200,
        required=False,
        label=_("Наименование источника"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Например: Список сотрудников 2024"),
            }
        ),
        help_text=_("Если не заполнено, будет использовано исходное имя файла."),
    )
    file = forms.FileField(
        required=True,
        label=_("Файл таблицы (CSV или XLSX)"),
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv,.xlsx",
            }
        ),
        help_text=_("Максимальный размер: 20 МБ. Поддерживаются форматы .csv и .xlsx."),
    )
    sheet_name = forms.CharField(
        max_length=150,
        required=False,
        label=_("Имя листа таблицы"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Оставьте пустым для первого активного листа"),
            }
        ),
        help_text=_("Применяется только для файлов Excel (.xlsx)."),
    )
    description = forms.CharField(
        max_length=1000,
        required=False,
        label=_("Описание источника данных"),
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": _("Краткое пояснение содержимого набора данных..."),
            }
        ),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            raise forms.ValidationError(_("Файл таблицы не выбран."))
        DataSourceSecurityValidator.validate_file(uploaded_file)
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get("file")
        name = cleaned_data.get("name")
        if not name and file:
            base_name = os.path.splitext(file.name)[0].replace("_", " ").strip()
            cleaned_data["name"] = base_name or _("Набор данных")
        return cleaned_data


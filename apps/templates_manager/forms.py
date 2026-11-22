"""Forms for uploading and managing DOCX templates."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.templates_manager.models import Template, TemplateStatus
from apps.templates_manager.services import DocxSecurityValidator, TemplateValidationError


class TemplateUploadForm(forms.ModelForm):
    """Form for uploading DOCX template files and specifying version parameters."""

    class Meta:
        model = Template
        fields = ["name", "file", "status", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Необязательно (по умолчанию берется имя файла)"),
                }
            ),
            "file": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": _("Что изменилось в этой версии шаблона..."),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["status"].initial = TemplateStatus.ACTIVE

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            raise forms.ValidationError(_("Пожалуйста, выберите DOCX-файл для загрузки."))

        try:
            DocxSecurityValidator.validate_file(uploaded_file, filename=uploaded_file.name)
        except TemplateValidationError as exc:
            raise forms.ValidationError(str(exc)) from exc

        return uploaded_file

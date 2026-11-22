"""Forms for Document Types management."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.documents.models import DocumentType


class DocumentTypeForm(forms.ModelForm):
    """Form for creating and editing document types."""

    class Meta:
        model = DocumentType
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Например: Трудовой договор, Акт приёма-передачи"),
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Краткое назначение и область применения документа..."),
                }
            ),
        }

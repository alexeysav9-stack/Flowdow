"""Forms for Organization details and settings."""

from django import forms

from apps.organizations.models import Organization, OrganizationSettings


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "legal_name", "tax_id", "email", "phone", "address", "website"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "legal_name": forms.TextInput(attrs={"class": "form-control"}),
            "tax_id": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
        }


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = OrganizationSettings
        fields = ["default_date_format", "default_currency", "retention_days"]
        widgets = {
            "default_date_format": forms.TextInput(attrs={"class": "form-control"}),
            "default_currency": forms.TextInput(attrs={"class": "form-control"}),
            "retention_days": forms.NumberInput(attrs={"class": "form-control"}),
        }

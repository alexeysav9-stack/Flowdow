"""Authentication and Profile forms for Accounts module."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from apps.accounts.models import User


class LoginForm(AuthenticationForm):
    """Standard B2B styled login form."""

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Username or Email",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Password",
            }
        )
    )


class UserProfileForm(forms.ModelForm):
    """Form allowing users to update their personal profile info."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "job_title", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }


class CustomUserCreationForm(UserCreationForm):
    """Admin form for user creation."""

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "job_title")


class CustomUserChangeForm(UserChangeForm):
    """Admin form for editing user."""

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "job_title",
            "is_active",
            "is_staff",
        )

"""Django admin configuration for custom User."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.forms import CustomUserChangeForm, CustomUserCreationForm
from apps.accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin representation for custom Flowdow user."""

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "job_title",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "job_title")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "job_title", "phone")}),
        (
            "Permissions & Role",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "role", "job_title", "password", "password_2"),
            },
        ),
    )

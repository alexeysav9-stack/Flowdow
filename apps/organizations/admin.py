"""Admin configuration for Organization."""

from django.contrib import admin

from apps.organizations.models import Organization, OrganizationSettings


class OrganizationSettingsInline(admin.StackedInline):
    model = OrganizationSettings
    can_delete = False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "tax_id", "email", "created_at")
    inlines = [OrganizationSettingsInline]

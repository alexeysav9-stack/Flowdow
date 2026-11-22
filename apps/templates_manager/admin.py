"""Admin configuration for Template."""

from django.contrib import admin

from apps.templates_manager.models import Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "version", "status", "created_at")
    list_filter = ("status", "document_type")
    search_fields = ("name", "document_type__name", "description")
    readonly_fields = ("created_at", "updated_at", "version", "detected_variables")

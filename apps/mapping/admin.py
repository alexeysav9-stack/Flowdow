"""Admin configuration for FieldMappingSchema."""

from django.contrib import admin

from apps.mapping.models import FieldMappingSchema


@admin.register(FieldMappingSchema)
class FieldMappingSchemaAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "data_source", "created_at")
    search_fields = ("name", "template__title")

"""Admin configuration for DataSource and DataRecord."""

from django.contrib import admin

from apps.data_sources.models import DataRecord, DataSource


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "format", "status", "row_count", "column_count", "created_at")
    list_filter = ("format", "status")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at", "row_count", "column_count", "headers")


@admin.register(DataRecord)
class DataRecordAdmin(admin.ModelAdmin):
    list_display = ("data_source", "row_number", "created_at")
    list_filter = ("data_source",)
    search_fields = ("data_source__name",)
    readonly_fields = ("created_at", "updated_at")

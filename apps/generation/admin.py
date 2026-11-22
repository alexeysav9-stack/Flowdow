"""Admin configuration for GenerationBatch."""

from django.contrib import admin

from apps.generation.models import GenerationBatch


@admin.register(GenerationBatch)
class GenerationBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "template",
        "data_source",
        "status",
        "processed_records",
        "total_records",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("template__title", "error_message")

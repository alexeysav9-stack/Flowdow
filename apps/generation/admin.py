"""Admin configuration for GenerationBatch and GeneratedDocument."""

from django.contrib import admin

from apps.generation.models import GeneratedDocument, GenerationBatch


class GeneratedDocumentInline(admin.TabularInline):
    model = GeneratedDocument
    extra = 0
    readonly_fields = ("data_record", "status", "error_message", "created_at")


@admin.register(GenerationBatch)
class GenerationBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "template",
        "data_source",
        "status",
        "successful_records",
        "failed_records",
        "total_records",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("template__name", "error_message")
    inlines = [GeneratedDocumentInline]


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "data_record", "status", "created_at")
    list_filter = ("status", "batch")
    search_fields = ("record_identifier", "error_message")

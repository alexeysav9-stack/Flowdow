"""Admin configuration for MappingConfig and MappingRule."""

from django.contrib import admin

from apps.mapping.models import MappingConfig, MappingRule


class MappingRuleInline(admin.TabularInline):
    model = MappingRule
    extra = 1


@admin.register(MappingConfig)
class MappingConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "data_source", "created_by", "created_at")
    list_filter = ("template", "data_source")
    search_fields = ("name", "description")
    inlines = [MappingRuleInline]


@admin.register(MappingRule)
class MappingRuleAdmin(admin.ModelAdmin):
    list_display = ("mapping_config", "template_variable", "source_column", "required")
    list_filter = ("required", "mapping_config")
    search_fields = ("template_variable", "source_column")

"""Admin configuration for AuditLog."""

from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "resource_type", "resource_id", "ip_address")
    list_filter = ("action", "resource_type", "created_at")
    search_fields = ("action", "resource_type", "resource_id", "user__username")
    readonly_fields = (
        "created_at",
        "updated_at",
        "user",
        "action",
        "resource_type",
        "resource_id",
        "ip_address",
        "details",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

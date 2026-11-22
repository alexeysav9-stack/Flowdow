"""Audit log model for activity tracking."""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AuditLog(TimeStampedModel):
    """Immutable audit entry recording system actions and mutations."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="User",
    )
    action = models.CharField(
        max_length=64,
        verbose_name="Action Type",
        help_text="Machine identifier of the action (e.g. USER_LOGIN, TEMPLATE_UPLOAD).",
    )
    resource_type = models.CharField(
        max_length=64,
        verbose_name="Resource Type",
        help_text="Target entity class name (e.g. User, DocumentTemplate, Batch).",
    )
    resource_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Resource ID",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP Address",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Action Details",
        help_text="Structured context parameters or diff values.",
    )

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        user_name = self.user.username if self.user else "System"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {user_name} -> {self.action} on {self.resource_type}:{self.resource_id}"

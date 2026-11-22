"""Audit service for recording compliance trails."""

from typing import Any

from django.contrib.auth import get_user_model

UserModel = get_user_model()


class AuditService:
    """Service for creating system and user activity audit records."""

    @classmethod
    def log(
        cls,
        action: str,
        resource_type: str,
        user: Any | None = None,
        resource_id: str = "",
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> Any:
        """Safely creates an audit record."""
        from apps.audit.models import AuditLog

        # Ensure user is valid model instance or None
        log_user = user if (user and getattr(user, "is_authenticated", False)) else None

        try:
            return AuditLog.objects.create(
                user=log_user,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                details=details or {},
                ip_address=ip_address,
            )
        except Exception:
            # Audit logging must never crash primary business transactions
            return None

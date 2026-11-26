"""Core services and selectors."""

import logging
from typing import Any

from django.db import connection

from apps.core.permissions import can_view_audit_logs, scope_generation_batches

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates metrics and statistics for the main operations dashboard."""

    @classmethod
    def get_metrics(cls, user: Any | None = None) -> dict[str, Any]:
        """Calculates system summary metrics across all domain modules."""
        # Using late imports to avoid circular dependencies
        from apps.audit.models import AuditLog
        from apps.data_sources.models import DataSource
        from apps.documents.models import DocumentType
        from apps.generation.models import GenerationBatch
        from apps.templates_manager.models import DocumentTemplate

        total_document_types = DocumentType.objects.count()
        total_templates = DocumentTemplate.objects.count()
        total_data_sources = DataSource.objects.count()

        batch_qs = GenerationBatch.objects.all()
        if user is not None:
            batch_qs = scope_generation_batches(batch_qs, user)

        total_batches = batch_qs.count()
        completed_batches = batch_qs.filter(status="COMPLETED").count()
        recent_batches = list(batch_qs.select_related("template").order_by("-created_at")[:5])

        if user is None or can_view_audit_logs(user):
            recent_activities = list(
                AuditLog.objects.select_related("user").order_by("-created_at")[:6]
            )
        else:
            recent_activities = []

        return {
            "total_document_types": total_document_types,
            "total_templates": total_templates,
            "total_data_sources": total_data_sources,
            "total_batches": total_batches,
            "completed_batches": completed_batches,
            "recent_batches": recent_batches,
            "recent_activities": recent_activities,
        }


class HealthCheckService:
    """Verifies internal system and infrastructure health."""

    @classmethod
    def check_health(cls) -> dict[str, Any]:
        """Tests database connectivity and application status without exposing internals."""
        db_healthy = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                db_healthy = row is not None and row[0] == 1
        except Exception:
            logger.exception("Health check database probe failed")

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": {
                "healthy": db_healthy,
            },
        }

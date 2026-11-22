"""Core services and selectors."""

from typing import Any

from django.db import connection


class DashboardService:
    """Aggregates metrics and statistics for the main operations dashboard."""

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
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
        total_batches = GenerationBatch.objects.count()

        completed_batches = GenerationBatch.objects.filter(status="COMPLETED").count()
        recent_batches = list(
            GenerationBatch.objects.select_related("template").order_by("-created_at")[:5]
        )
        recent_activities = list(
            AuditLog.objects.select_related("user").order_by("-created_at")[:6]
        )

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
        """Tests database connectivity and application status."""
        db_healthy = False
        db_error = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                db_healthy = row is not None and row[0] == 1
        except Exception as exc:
            db_error = str(exc)

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": {
                "healthy": db_healthy,
                "vendor": connection.vendor,
                "error": db_error,
            },
        }

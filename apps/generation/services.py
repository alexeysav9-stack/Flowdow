"""Service layer for document generation."""

import io
from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.data_sources.models import DataSource
from apps.generation.models import BatchStatus, GenerationBatch
from apps.templates_manager.models import DocumentTemplate


class DocumentGenerationService:
    """Orchestrates single and batch document generation."""

    @classmethod
    def create_batch(
        cls,
        template: DocumentTemplate,
        user: User | None = None,
        data_source: DataSource | None = None,
        total_records: int = 1,
    ) -> GenerationBatch:
        """Initializes a new generation batch record."""
        with transaction.atomic():
            batch = GenerationBatch.objects.create(
                template=template,
                data_source=data_source,
                initiated_by=user,
                status=BatchStatus.PENDING,
                total_records=total_records,
                processed_records=0,
            )
            return batch

    @classmethod
    def render_template_to_stream(cls, template_path: str, context: dict[str, Any]) -> io.BytesIO:
        """Renders docxtpl template with given context dictionary into in-memory stream."""
        from docxtpl import DocxTemplate

        doc = DocxTemplate(template_path)
        doc.render(context)
        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        return output_stream

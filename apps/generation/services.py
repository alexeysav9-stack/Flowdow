"""Service layer for single and batch document generation via docxtpl."""

import io
import os
import re
import zipfile
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from docxtpl import DocxTemplate

from apps.accounts.models import UserRole
from apps.audit.services import AuditService
from apps.data_sources.models import DataRecord
from apps.generation.models import (
    BatchStatus,
    GeneratedDocument,
    GenerationBatch,
    GenerationDocumentStatus,
)
from apps.mapping.models import MappingConfig
from apps.mapping.services import MappingValidationService
from apps.templates_manager.models import Template, TemplateStatus

UserModel = get_user_model()


class GenerationError(Exception):
    """Raised when document generation fails."""

    pass


class GenerationValidationError(Exception):
    """Raised when pre-generation validation fails."""

    pass


def can_generate_documents(user: Any) -> bool:
    """Checks whether the user has rights to execute document generation."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    user_role = getattr(user, "role", None)
    return user_role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR}


class GenerationPermissionMixin(UserPassesTestMixin):
    """View mixin enforcing document generation permissions."""

    def test_func(self) -> bool:
        return can_generate_documents(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(
            _("У вашей роли недостаточно прав для запуска генерации документов.")
        )


def sanitize_filename(name: str, fallback: str = "document") -> str:
    """Removes filesystem-unsafe characters to prevent path traversal or broken filenames."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned[:80] or fallback


class DocumentGenerationService:
    """Orchestrates single and batch document generation."""

    @classmethod
    def create_batch(
        cls,
        template: Template,
        user: Any | None = None,
        data_source: Any | None = None,
        mapping_config: MappingConfig | None = None,
        total_records: int = 1,
    ) -> GenerationBatch:
        """Initializes a new generation batch record (preserves backward compatibility)."""
        with transaction.atomic():
            batch = GenerationBatch.objects.create(
                template=template,
                data_source=data_source,
                mapping_config=mapping_config,
                initiated_by=user if (user and getattr(user, "is_authenticated", False)) else None,
                status=BatchStatus.PENDING,
                total_records=total_records,
                processed_records=0,
            )
            return batch

    @classmethod
    def render_template_to_stream(
        cls,
        template_path: str,
        context: dict[str, Any],
    ) -> io.BytesIO:
        """Renders docxtpl template with given context dictionary into in-memory stream."""
        doc = DocxTemplate(template_path)
        doc.render(context)
        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        return output_stream

    @classmethod
    def generate_single_document(
        cls,
        template: Template,
        mapping_config: MappingConfig,
        data_record: DataRecord,
        batch: GenerationBatch,
    ) -> GeneratedDocument:
        """Renders a single DOCX document for a specific DataRecord within a batch.

        Isolates errors so that individual record failures do not halt batch execution.
        """
        # Determine human-readable identifier for record
        record_id_str = f"Row #{data_record.row_number}"
        first_val = next(
            (str(v).strip() for v in data_record.data.values() if str(v).strip()),
            "",
        )
        if first_val:
            record_id_str = f"Row #{data_record.row_number} ({first_val[:30]})"

        # 1. Build and validate record context
        context, errors = MappingValidationService.build_record_context(
            mapping_config=mapping_config,
            record_data=data_record.data,
            row_number=data_record.row_number,
        )

        if errors:
            return GeneratedDocument.objects.create(
                batch=batch,
                data_record=data_record,
                status=GenerationDocumentStatus.FAILED,
                error_message="; ".join(errors),
                record_identifier=record_id_str,
            )

        # 2. Render DOCX template
        try:
            if not template.file or not os.path.exists(template.file.path):
                raise GenerationError(_("Файл шаблона отсутствует на сервере."))

            rendered_stream = cls.render_template_to_stream(template.file.path, context)

            # Generate predictable, sanitized filename
            clean_tmpl = slugify(template.name) or "doc"
            clean_val = (
                sanitize_filename(first_val) if first_val else f"rec_{data_record.row_number}"
            )
            doc_filename = f"{clean_tmpl}_rec{data_record.row_number}_{clean_val}.docx"

            doc_record = GeneratedDocument(
                batch=batch,
                data_record=data_record,
                status=GenerationDocumentStatus.SUCCESS,
                record_identifier=record_id_str,
            )
            doc_record.file.save(doc_filename, ContentFile(rendered_stream.getvalue()), save=True)
            return doc_record

        except Exception as err:
            return GeneratedDocument.objects.create(
                batch=batch,
                data_record=data_record,
                status=GenerationDocumentStatus.FAILED,
                error_message=str(err),
                record_identifier=record_id_str,
            )

    @classmethod
    def generate_batch(
        cls,
        mapping_config: MappingConfig,
        data_records: list[DataRecord],
        user: Any | None = None,
    ) -> GenerationBatch:
        """Executes batch document generation synchronously across selected records.

        Produces individual DOCX files, captures isolated record errors, and compiles
        a ZIP archive of all successfully created documents.
        """
        template = mapping_config.template
        data_source = mapping_config.data_source

        # 1. Pre-generation validation of template & mapping config
        if template.status != TemplateStatus.ACTIVE:
            raise GenerationValidationError(
                _("Шаблон «%(name)s» v%(ver)d не активен. Генерация невозможна.")
                % {"name": template.name, "ver": template.version}
            )

        is_valid, config_errors = MappingValidationService.validate_mapping_config(mapping_config)
        if not is_valid:
            raise GenerationValidationError("; ".join(config_errors))

        if not data_records:
            raise GenerationValidationError(
                _("Не выбрано ни одной записи для формирования документов.")
            )

        # 2. Create batch record in PROCESSING status
        with transaction.atomic():
            batch = GenerationBatch.objects.create(
                template=template,
                data_source=data_source,
                mapping_config=mapping_config,
                initiated_by=user if (user and getattr(user, "is_authenticated", False)) else None,
                status=BatchStatus.PROCESSING,
                total_records=len(data_records),
                processed_records=0,
                successful_records=0,
                failed_records=0,
            )

        # 3. Process each record with isolated error handling
        successful_docs: list[GeneratedDocument] = []
        for record in data_records:
            doc = cls.generate_single_document(
                template=template,
                mapping_config=mapping_config,
                data_record=record,
                batch=batch,
            )
            batch.processed_records += 1
            if doc.status == GenerationDocumentStatus.SUCCESS:
                batch.successful_records += 1
                successful_docs.append(doc)
            else:
                batch.failed_records += 1

        # 4. Compile ZIP archive of successful documents
        if successful_docs:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for doc in successful_docs:
                    if doc.file and os.path.exists(doc.file.path):
                        arcname = os.path.basename(doc.file.name)
                        zf.write(doc.file.path, arcname=arcname)

            zip_filename = f"batch_{batch.id}_{slugify(template.name) or 'docs'}.zip"
            batch.output_file.save(zip_filename, ContentFile(zip_buffer.getvalue()), save=False)

        # 5. Finalize batch status
        if batch.successful_records > 0:
            batch.status = BatchStatus.COMPLETED
        else:
            batch.status = BatchStatus.FAILED
            batch.error_message = _("Ни один документ не был сформирован из-за ошибок валидации.")

        batch.save()

        AuditService.log(
            action="GENERATION_BATCH_COMPLETED",
            resource_type="GenerationBatch",
            resource_id=str(batch.id),
            user=user,
            details={
                "template": template.name,
                "data_source": data_source.name if data_source else "",
                "total": batch.total_records,
                "success": batch.successful_records,
                "failed": batch.failed_records,
                "status": batch.status,
            },
        )
        return batch

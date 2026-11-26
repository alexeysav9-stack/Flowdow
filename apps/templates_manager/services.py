"""Service layer for inspecting, validating, and managing DOCX templates."""

import logging
import os
import re
from typing import Any

import docxtpl
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit.services import AuditService
from apps.core.archive_security import get_actual_stream_size, validate_docx_archive
from apps.core.permissions import can_manage_documents, require_permission
from apps.core.template_security import (
    TemplateError,
    TemplateSecurityError,
    inspect_and_validate_docx,
)
from apps.documents.models import DocumentType
from apps.templates_manager.models import Template, TemplateStatus

logger = logging.getLogger(__name__)

# Regex for basic placeholder matching in legacy plain-text helper
PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([^\W\d]\w*)(?:\s*\|[^\}]+)?\s*\}\}")

# Default max file size: 10 MB
MAX_TEMPLATE_FILE_SIZE = getattr(settings, "FLOWDOW_MAX_TEMPLATE_FILE_SIZE", 10 * 1024 * 1024)
MAX_UNCOMPRESSED_RATIO = 100
MAX_TOTAL_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB


class TemplateValidationError(ValidationError):
    """Raised when uploaded template fails validation or security checks."""

    pass


class DocxSecurityValidator:
    """Security validation engine for uploaded DOCX templates."""

    @classmethod
    def validate_file(cls, file_obj: Any, filename: str = "") -> None:
        """Validates file size, extension, ZIP/OOXML structure, zip-bomb bounds, and XML safety."""
        declared_size = getattr(file_obj, "size", None)
        actual_size = get_actual_stream_size(file_obj)
        size = max(actual_size, int(declared_size or 0))

        if size == 0:
            raise TemplateValidationError(_("Загруженный файл пуст."))

        if size > MAX_TEMPLATE_FILE_SIZE:
            max_mb = MAX_TEMPLATE_FILE_SIZE // (1024 * 1024)
            raise TemplateValidationError(
                _("Размер файла превышает максимально допустимый лимит (%(max_mb)d МБ).")
                % {"max_mb": max_mb}
            )

        name_to_check = filename or getattr(file_obj, "name", "")
        if name_to_check:
            clean_name = os.path.basename(name_to_check)
            _root, ext = os.path.splitext(clean_name)
            if ext.lower() != ".docx":
                raise TemplateValidationError(
                    _("Недопустимое расширение файла '%(ext)s'. Разрешены только файлы .docx.")
                    % {"ext": ext}
                )

        validate_docx_archive(
            file_obj,
            max_file_size=MAX_TEMPLATE_FILE_SIZE,
            max_uncompressed_size=MAX_TOTAL_UNCOMPRESSED_SIZE,
            max_decompression_ratio=MAX_UNCOMPRESSED_RATIO,
            error_cls=TemplateValidationError,
        )


class TemplateInspectionService:
    """Discovers and validates template placeholders using docxtpl and strict Jinja2 AST rules."""

    @classmethod
    def extract_variables_from_text(cls, content: str) -> list[str]:
        """Extracts unique placeholder variable names from template text (legacy regex helper)."""
        matches: set[str] = set(PLACEHOLDER_REGEX.findall(content))
        return sorted(matches)

    @classmethod
    def inspect_file(cls, file_source: Any, filename: str = "") -> list[str]:
        """Inspects DOCX template and returns a unique sorted list of discovered variable names.

        Handles Word's internal split XML runs gracefully using docxtpl and enforces the
        unified strict Jinja2 AST allowlist across all rendered DOCX parts.
        """
        # 1. Run structural and archive security validation first
        DocxSecurityValidator.validate_file(file_source, filename=filename)

        # 2. Parse, AST-validate, and extract variables via unified safe Jinja2 engine
        try:
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            doc = docxtpl.DocxTemplate(file_source)
            return inspect_and_validate_docx(doc)
        except TemplateSecurityError as exc:
            logger.warning("Rejected unsafe DOCX template syntax: %s", exc)
            raise TemplateValidationError(str(exc)) from exc
        except TemplateError as exc:
            logger.warning("Rejected invalid DOCX Jinja2 syntax: %s", type(exc).__name__)
            raise TemplateValidationError(
                _("Синтаксическая ошибка в Jinja2-разметке шаблона DOCX.")
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during DOCX template inspection")
            raise TemplateValidationError(
                _("Не удалось проверить шаблон DOCX. Проверьте корректность файла.")
            ) from exc
        finally:
            if hasattr(file_source, "seek"):
                file_source.seek(0)


class TemplateService:
    """Service orchestrating Template lifecycle, versioning, and status transitions."""

    @classmethod
    def get_next_version(cls, document_type: DocumentType) -> int:
        """Determines the next version number for a document type."""
        latest = Template.objects.filter(document_type=document_type).order_by("-version").first()
        return (latest.version + 1) if latest else 1

    @classmethod
    def create_template_version(
        cls,
        document_type: DocumentType,
        file_obj: Any = None,
        name: str = "",
        description: str = "",
        status: str = TemplateStatus.ACTIVE,
        user: User | None = None,
        **kwargs: Any,
    ) -> Template:
        """Validates, inspects, and creates a new versioned template.

        Guarantees that old template files are never overwritten.
        """
        if file_obj is None and "uploaded_file" in kwargs:
            file_obj = kwargs["uploaded_file"]
        if user is not None:
            require_permission(
                can_manage_documents(user),
                _("У вашей роли недостаточно прав для загрузки шаблонов."),
            )
        original_name = getattr(file_obj, "name", "template.docx")
        if not name:
            clean_name = os.path.basename(original_name)
            name, _ext = os.path.splitext(clean_name)
            name = name.replace("_", " ").title()

        # 1. Inspect and extract variables (validates security inside)
        detected_vars = TemplateInspectionService.inspect_file(file_obj, filename=original_name)

        with transaction.atomic():
            next_version = cls.get_next_version(document_type)

            # If newly created template is active, archive previous active versions
            if status == TemplateStatus.ACTIVE:
                Template.objects.filter(
                    document_type=document_type, status=TemplateStatus.ACTIVE
                ).update(status=TemplateStatus.ARCHIVED)

            template = Template.objects.create(
                document_type=document_type,
                name=name,
                file=file_obj,
                version=next_version,
                status=status,
                description=description,
                detected_variables=detected_vars,
            )

            AuditService.log(
                action="TEMPLATE_UPLOADED",
                resource_type="Template",
                resource_id=str(template.id),
                user=user,
                details={
                    "document_type_id": document_type.id,
                    "document_type_name": document_type.name,
                    "version": template.version,
                    "variables_count": len(detected_vars),
                    "variables": detected_vars,
                },
            )

            return template

    @classmethod
    def activate_template(cls, template: Template, user: User | None = None) -> Template:
        """Activates template and archives any other active versions for the document type."""
        if user is not None:
            require_permission(
                can_manage_documents(user),
                _("У вашей роли недостаточно прав для активации шаблонов."),
            )
        with transaction.atomic():
            Template.objects.filter(
                document_type=template.document_type, status=TemplateStatus.ACTIVE
            ).exclude(id=template.id).update(status=TemplateStatus.ARCHIVED)

            template.status = TemplateStatus.ACTIVE
            template.save(update_fields=["status", "updated_at"])

            AuditService.log(
                action="TEMPLATE_ACTIVATED",
                resource_type="Template",
                resource_id=str(template.id),
                user=user,
                details={
                    "document_type_id": template.document_type_id,
                    "version": template.version,
                },
            )
            return template

    @classmethod
    def archive_template(cls, template: Template, user: User | None = None) -> Template:
        """Transitions template to archived status."""
        if user is not None:
            require_permission(
                can_manage_documents(user),
                _("У вашей роли недостаточно прав для архивации шаблонов."),
            )
        template.status = TemplateStatus.ARCHIVED
        template.save(update_fields=["status", "updated_at"])

        AuditService.log(
            action="TEMPLATE_ARCHIVED",
            resource_type="Template",
            resource_id=str(template.id),
            user=user,
            details={
                "document_type_id": template.document_type_id,
                "version": template.version,
            },
        )
        return template

"""Service layer for inspecting, validating, and managing DOCX templates."""

import io
import os
import re
import zipfile
from typing import Any

import docxtpl
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit.services import AuditService
from apps.documents.models import DocumentType
from apps.templates_manager.models import Template, TemplateStatus

# Variable regex for basic placeholder matching: letters, numbers, underscore
VALID_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\|[^\}]+)?\s*\}\}")

# Default max file size: 10 MB
MAX_TEMPLATE_FILE_SIZE = getattr(settings, "FLOWDOW_MAX_TEMPLATE_FILE_SIZE", 10 * 1024 * 1024)
MAX_UNCOMPRESSED_RATIO = 100
MAX_TOTAL_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB


class TemplateValidationError(ValidationError):
    """Raised when uploaded template fails validation or security checks."""

    pass


class DocxSecurityValidator:
    """Security validation engine for uploaded DOCX templates.

    Guarantees that files:
    1. Do not exceed file size limits.
    2. Have valid .docx extension.
    3. Start with ZIP magic header (PK\x03\x04).
    4. Are well-formed OpenXML archives containing word/document.xml.
    5. Are not decompression bombs (zip bombs).
    6. Do not contain dangerous executable payloads.
    """

    DANGEROUS_EXTENSIONS = {
        ".exe",
        ".bat",
        ".cmd",
        ".vbs",
        ".sh",
        ".bin",
        ".msi",
        ".jar",
        ".ps1",
    }

    @classmethod
    def validate_file(cls, file_obj: Any, filename: str = "") -> None:
        """Validates file integrity and security."""
        # 1. File size check
        size = getattr(file_obj, "size", None)
        if size is None:
            if hasattr(file_obj, "seek") and hasattr(file_obj, "tell"):
                pos = file_obj.tell()
                file_obj.seek(0, os.SEEK_END)
                size = file_obj.tell()
                file_obj.seek(pos)

        if size and size > MAX_TEMPLATE_FILE_SIZE:
            max_mb = MAX_TEMPLATE_FILE_SIZE // (1024 * 1024)
            raise TemplateValidationError(
                _("Размер файла превышает максимально допустимый лимит (%(max_mb)d МБ).")
                % {"max_mb": max_mb}
            )

        if size == 0:
            raise TemplateValidationError(_("Загруженный файл пуст."))

        # 2. Extension check
        name_to_check = filename or getattr(file_obj, "name", "")
        if name_to_check:
            clean_name = os.path.basename(name_to_check)
            _root, ext = os.path.splitext(clean_name)
            if ext.lower() != ".docx":
                raise TemplateValidationError(
                    _("Недопустимое расширение файла '%(ext)s'. Разрешены только файлы .docx.")
                    % {"ext": ext}
                )

        # 3. Magic bytes check (ZIP header PK\x03\x04)
        if hasattr(file_obj, "seek") and hasattr(file_obj, "read"):
            initial_pos = file_obj.tell()
            file_obj.seek(0)
            magic = file_obj.read(4)
            file_obj.seek(initial_pos)

            if magic != b"PK\x03\x04":
                raise TemplateValidationError(
                    _("Файл не является корректным DOCX-документом (неверная сигнатура ZIP).")
                )

        # 4. ZIP container and structural integrity
        target = file_obj
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
            target = io.BytesIO(file_obj.read())
            file_obj.seek(0)

        if not zipfile.is_zipfile(target):
            raise TemplateValidationError(_("Файл повреждён или не является валидным ZIP-архивом."))

        try:
            with zipfile.ZipFile(target, "r") as archive:
                # Test archive integrity
                bad_file = archive.testzip()
                if bad_file:
                    raise TemplateValidationError(
                        _("Архив шаблона повреждён (ошибка в элементе '%(name)s').")
                        % {"name": bad_file}
                    )

                namelist = archive.namelist()

                # Verify OpenXML standard entry
                if "word/document.xml" not in namelist:
                    raise TemplateValidationError(
                        _(
                            "Файл не является документом Word DOCX: отсутствует компонент word/document.xml."
                        )
                    )

                # Check for zip bomb and prohibited payloads
                total_uncompressed = 0
                compressed_size = size or 1

                for info in archive.infolist():
                    _entry_root, entry_ext = os.path.splitext(info.filename)
                    if entry_ext.lower() in cls.DANGEROUS_EXTENSIONS:
                        raise TemplateValidationError(
                            _("В архиве обнаружен недопустимый файл '%(name)s'.")
                            % {"name": info.filename}
                        )

                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_SIZE:
                        raise TemplateValidationError(
                            _("Общий распакованный объём документа превышает лимит безопасности.")
                        )

                ratio = total_uncompressed / max(compressed_size, 1)
                if ratio > MAX_UNCOMPRESSED_RATIO:
                    raise TemplateValidationError(
                        _("Обнаружен аномальный коэффициент сжатия (возможная zip-бомба).")
                    )

        except zipfile.BadZipFile as exc:
            raise TemplateValidationError(
                _("Не удалось прочитать DOCX архив: %(err)s") % {"err": str(exc)}
            ) from exc


class TemplateInspectionService:
    """Discovers and parses template placeholders using docxtpl and Jinja2 AST."""

    @classmethod
    def extract_variables_from_text(cls, content: str) -> list[str]:
        """Extracts unique placeholder variable names from template text (fallback/unit tests)."""
        matches: set[str] = set(PLACEHOLDER_REGEX.findall(content))
        return sorted(matches)

    @classmethod
    def inspect_file(cls, file_source: Any, filename: str = "") -> list[str]:
        """Inspects DOCX template and returns a unique sorted list of discovered variable names.

        Handles Word's internal split XML runs gracefully using docxtpl/Jinja2 AST.
        Rejects arbitrary Python execution and allows only safe identifiers.
        """
        # 1. Run security validation first
        DocxSecurityValidator.validate_file(file_source, filename=filename)

        # 2. Extract undeclared variables via docxtpl
        try:
            if hasattr(file_source, "seek"):
                file_source.seek(0)
                # docxtpl accepts file path or file-like object
                doc = docxtpl.DocxTemplate(file_source)
                file_source.seek(0)
            else:
                doc = docxtpl.DocxTemplate(file_source)

            raw_variables = doc.get_undeclared_template_variables()
        except Exception as exc:
            raise TemplateValidationError(
                _("Синтаксическая ошибка в Jinja2-разметке шаблона DOCX: %(err)s")
                % {"err": str(exc)}
            ) from exc

        # 3. Filter and validate variable names: must be valid identifiers
        valid_variables: set[str] = set()
        for var in raw_variables:
            var_str = str(var).strip()
            # Do not allow dunder variables or non-identifiers
            if (
                var_str
                and not var_str.startswith("__")
                and VALID_IDENTIFIER_REGEX.match(var_str)
                and not hasattr(__builtins__, var_str)
            ):
                valid_variables.add(var_str)

        return sorted(valid_variables)


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
        original_name = getattr(file_obj, "name", "template.docx")
        if not name:
            clean_name = os.path.basename(original_name)
            name, _ = os.path.splitext(clean_name)
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

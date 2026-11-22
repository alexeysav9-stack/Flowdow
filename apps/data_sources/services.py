"""Services for parsing, validating, and managing CSV and XLSX data sources."""

import csv
import datetime
import io
import os
import zipfile
from collections import Counter
from typing import Any

import openpyxl
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Page, Paginator
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import UserRole
from apps.audit.services import AuditService
from apps.data_sources.constants import (
    ALLOWED_DATA_EXTENSIONS,
    CSV_CANDIDATE_DELIMITERS,
    MAX_DATA_SOURCE_COLUMNS,
    MAX_DATA_SOURCE_FILE_SIZE,
    MAX_DATA_SOURCE_ROWS,
    MAX_XLSX_DECOMPRESSION_RATIO,
    MAX_XLSX_UNCOMPRESSED_SIZE,
)
from apps.data_sources.models import DataRecord, DataSource, DataSourceFormat, DataSourceStatus

UserModel = get_user_model()


class DataSourceValidationError(Exception):
    """Raised when uploaded file violates security, size, or structure constraints."""

    pass


class DataSourceImportError(Exception):
    """Raised when parsing or database insertion fails."""

    pass


def can_manage_data_sources(user: Any) -> bool:
    """Checks whether the user has privileges to upload or delete data sources."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    user_role = getattr(user, "role", None)
    return user_role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR}


class DataSourcePermissionMixin(UserPassesTestMixin):
    """View mixin enforcing data source modification permissions."""

    def test_func(self) -> bool:
        return can_manage_data_sources(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(
            _("У вашей роли недостаточно прав для загрузки или удаления источников данных.")
        )


class DataSourceSecurityValidator:
    """Validates file size, extensions, magic numbers, and OpenXML integrity."""

    @classmethod
    def validate_file(cls, uploaded_file: Any) -> str:
        """Validates file safety.

        Returns detected format ('csv' or 'xlsx').
        """
        size = getattr(uploaded_file, "size", None)
        if size is None:
            uploaded_file.seek(0, os.SEEK_END)
            size = uploaded_file.tell()
            uploaded_file.seek(0)

        if size == 0:
            raise DataSourceValidationError(_("Загруженный файл пуст (0 байт)."))

        if size > MAX_DATA_SOURCE_FILE_SIZE:
            max_mb = MAX_DATA_SOURCE_FILE_SIZE // (1024 * 1024)
            raise DataSourceValidationError(
                _("Размер файла превышает допустимый предел %(max_mb)d МБ.") % {"max_mb": max_mb}
            )

        filename = getattr(uploaded_file, "name", "dataset")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_DATA_EXTENSIONS:
            raise DataSourceValidationError(
                _("Неподдерживаемый формат файла «%(ext)s». Разрешены только: .csv, .xlsx")
                % {"ext": ext}
            )

        uploaded_file.seek(0)
        prefix = uploaded_file.read(4096)
        uploaded_file.seek(0)

        if ext == ".xlsx":
            cls._validate_xlsx_archive(uploaded_file)
            return DataSourceFormat.XLSX
        else:
            cls._validate_csv_content(prefix)
            return DataSourceFormat.CSV

    @classmethod
    def _validate_xlsx_archive(cls, file_obj: Any) -> None:
        file_obj.seek(0)
        magic = file_obj.read(4)
        file_obj.seek(0)

        if magic != b"PK\x03\x04":
            raise DataSourceValidationError(
                _("Файл не является корректным архивом Excel SpreadsheetML (.xlsx).")
            )

        try:
            with zipfile.ZipFile(file_obj, "r") as zf:
                namelist = zf.namelist()
                has_workbook = any(name.startswith("xl/workbook") for name in namelist)
                has_content_types = "[Content_Types].xml" in namelist
                if not (has_workbook or has_content_types):
                    raise DataSourceValidationError(
                        _("Архив XLSX не содержит структуры рабочей книги Excel.")
                    )

                for name in namelist:
                    lower = name.lower()
                    if lower.endswith((".exe", ".sh", ".bat", ".vbs", ".cmd", ".ps1", ".py")):
                        raise DataSourceValidationError(
                            _("В архиве обнаружен недопустимый файл %(name)s.") % {"name": name}
                        )

                total_uncompressed = 0
                total_compressed = 0
                for info in zf.infolist():
                    total_uncompressed += info.file_size
                    total_compressed += info.compress_size

                if total_uncompressed > MAX_XLSX_UNCOMPRESSED_SIZE:
                    raise DataSourceValidationError(
                        _("Размер распакованных данных превышает лимит безопасности (100 МБ).")
                    )

                if total_compressed > 0:
                    ratio = total_uncompressed / total_compressed
                    if ratio > MAX_XLSX_DECOMPRESSION_RATIO:
                        raise DataSourceValidationError(
                            _("Подозрительно высокий коэффициент сжатия (возможная zip-бомба).")
                        )
        except zipfile.BadZipFile as err:
            raise DataSourceValidationError(
                _("Файл повреждён или не является валидным ZIP-контейнером.")
            ) from err
        finally:
            file_obj.seek(0)

    @classmethod
    def _validate_csv_content(cls, prefix: bytes) -> None:
        if b"\x00" in prefix:
            raise DataSourceValidationError(_("Файл CSV содержит бинарные нулевые байты."))


class CsvImportService:
    """Service for parsing CSV streams with UTF-8 / BOM support and delimiter autodetection."""

    @classmethod
    def detect_encoding_and_decode(cls, raw_bytes: bytes) -> str:
        """Decodes bytes to text supporting UTF-8 and UTF-8 with BOM."""
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode("cp1251")
            except UnicodeDecodeError as err:
                raise DataSourceValidationError(
                    _("Не удалось распознать кодировку CSV. Требуется UTF-8 или UTF-8 с BOM.")
                ) from err

    @classmethod
    def detect_delimiter(cls, text_sample: str) -> str:
        """Detects delimiter from a text sample using Sniffer and frequency counting."""
        lines = [line.strip() for line in text_sample.splitlines() if line.strip()]
        if not lines:
            return ","

        sample_for_sniffer = "\n".join(lines[:10])
        try:
            dialect = csv.Sniffer().sniff(sample_for_sniffer, delimiters=CSV_CANDIDATE_DELIMITERS)
            return dialect.delimiter
        except Exception:
            first_line = lines[0]
            counts = {delim: first_line.count(delim) for delim in CSV_CANDIDATE_DELIMITERS}
            best_delim = max(counts, key=counts.get)
            if counts[best_delim] > 0:
                return best_delim
            return ","

    @classmethod
    def parse_stream(
        cls,
        text_stream: io.StringIO | io.TextIOBase,
        max_rows: int = MAX_DATA_SOURCE_ROWS,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Parses CSV text stream into a list of unique headers and record dictionaries."""
        content = text_stream.read()
        if not content or not content.strip():
            raise DataSourceValidationError(_("Файл CSV пуст или не содержит данных."))

        delimiter = cls.detect_delimiter(content)
        stream = io.StringIO(content)
        reader = csv.reader(stream, delimiter=delimiter)

        # 1. Extract headers (skip leading blank lines)
        raw_headers: list[str] | None = None
        for row in reader:
            if any(cell.strip() for cell in row):
                raw_headers = row
                break

        if raw_headers is None:
            raise DataSourceValidationError(_("Файл CSV не содержит строк с данными."))

        # Trim trailing empty header columns
        raw_headers_list = [str(c).strip() for c in raw_headers]
        while raw_headers_list and not raw_headers_list[-1]:
            raw_headers_list.pop()

        if not raw_headers_list:
            raise DataSourceValidationError(_("Файл CSV не содержит заголовков колонок."))

        if len(raw_headers_list) > MAX_DATA_SOURCE_COLUMNS:
            raise DataSourceValidationError(
                _("Количество колонок (%(count)d) превышает допустимый лимит %(max)d.")
                % {"count": len(raw_headers_list), "max": MAX_DATA_SOURCE_COLUMNS}
            )

        # Check for empty column names
        for idx, h in enumerate(raw_headers_list, start=1):
            if not h:
                raise DataSourceValidationError(
                    _("Колонка №%(idx)d имеет пустой заголовок. Все колонки должны быть названы.")
                    % {"idx": idx}
                )

        # Check for duplicate column names
        counter = Counter(raw_headers_list)
        duplicates = [col for col, count in counter.items() if count > 1]
        if duplicates:
            formatted_dups = ", ".join(f"«{d}»" for d in duplicates)
            raise DataSourceValidationError(
                _("Обнаружены повторяющиеся названия колонок: %(cols)s.") % {"cols": formatted_dups}
            )

        headers = raw_headers_list
        header_len = len(headers)

        # 2. Extract data rows
        rows: list[dict[str, Any]] = []
        for row_idx, row in enumerate(reader, start=1):
            # Check if row is completely blank
            if not any(str(cell).strip() for cell in row):
                continue

            if len(rows) >= max_rows:
                raise DataSourceValidationError(
                    _("Файл превышает допустимый лимит строк (максимум %(max)d).")
                    % {"max": max_rows}
                )

            # Check if row has more cells than headers with non-empty values
            if len(row) > header_len:
                extra_cells = [str(c).strip() for c in row[header_len:] if str(c).strip()]
                if extra_cells:
                    raise DataSourceValidationError(
                        _("Строка %(row)d содержит %(actual)d колонок при ожидаемых %(expected)d.")
                        % {"row": row_idx, "actual": len(row), "expected": header_len}
                    )

            row_dict: dict[str, Any] = {}
            for col_idx, col_name in enumerate(headers):
                if col_idx < len(row):
                    row_dict[col_name] = str(row[col_idx]).strip()
                else:
                    row_dict[col_name] = ""
            rows.append(row_dict)

        if not rows:
            raise DataSourceValidationError(
                _("Файл CSV содержит заголовки, но не содержит строк данных.")
            )

        return headers, rows


class XlsxImportService:
    """Service for parsing XLSX files in streaming read_only mode."""

    @classmethod
    def get_sheet_names(cls, file_obj_or_path: Any) -> list[str]:
        """Returns the list of worksheet names from the workbook."""
        wb = openpyxl.load_workbook(file_obj_or_path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    @classmethod
    def parse_file(
        cls,
        file_obj_or_path: Any,
        sheet_name: str | None = None,
        max_rows: int = MAX_DATA_SOURCE_ROWS,
    ) -> tuple[list[str], list[dict[str, Any]], str]:
        """Parses an XLSX file using openpyxl in streaming mode.

        Returns (headers, rows, sheet_name_used).
        """
        wb = openpyxl.load_workbook(file_obj_or_path, read_only=True, data_only=True)
        try:
            available_sheets = wb.sheetnames
            if not available_sheets:
                raise DataSourceValidationError(_("Книга Excel не содержит ни одного листа."))

            if sheet_name and sheet_name in available_sheets:
                active_sheet = wb[sheet_name]
                used_sheet = sheet_name
            else:
                active_sheet = wb.active or wb[available_sheets[0]]
                used_sheet = active_sheet.title

            row_iterator = active_sheet.iter_rows(values_only=True)

            # Find first non-empty row as header
            raw_header_row: tuple[Any, ...] | None = None
            for row in row_iterator:
                if any(cell is not None and str(cell).strip() != "" for cell in row):
                    raw_header_row = row
                    break

            if raw_header_row is None:
                raise DataSourceValidationError(
                    _("Лист «%(sheet)s» пуст или не содержит данных.") % {"sheet": used_sheet}
                )

            # Trim trailing empty header columns
            raw_cells = list(raw_header_row)
            while raw_cells and (raw_cells[-1] is None or str(raw_cells[-1]).strip() == ""):
                raw_cells.pop()

            if not raw_cells:
                raise DataSourceValidationError(
                    _("Лист «%(sheet)s» не содержит заголовков колонок.") % {"sheet": used_sheet}
                )

            if len(raw_cells) > MAX_DATA_SOURCE_COLUMNS:
                raise DataSourceValidationError(
                    _("Количество колонок (%(count)d) превышает лимит %(max)d.")
                    % {"count": len(raw_cells), "max": MAX_DATA_SOURCE_COLUMNS}
                )

            headers = [cls._format_cell_value(cell) for cell in raw_cells]

            # Validate header names
            for idx, h in enumerate(headers, start=1):
                if not h:
                    raise DataSourceValidationError(
                        _("Колонка №%(idx)d на листе «%(sheet)s» имеет пустой заголовок.")
                        % {"idx": idx, "sheet": used_sheet}
                    )

            counter = Counter(headers)
            duplicates = [col for col, count in counter.items() if count > 1]
            if duplicates:
                formatted_dups = ", ".join(f"«{d}»" for d in duplicates)
                raise DataSourceValidationError(
                    _("На листе «%(sheet)s» обнаружены повторяющиеся заголовки: %(cols)s.")
                    % {"sheet": used_sheet, "cols": formatted_dups}
                )

            rows: list[dict[str, Any]] = []

            for row in row_iterator:
                # Skip empty row
                if not any(cell is not None and str(cell).strip() != "" for cell in row):
                    continue

                if len(rows) >= max_rows:
                    raise DataSourceValidationError(
                        _("Превышен допустимый лимит строк на листе (максимум %(max)d).")
                        % {"max": max_rows}
                    )

                row_dict: dict[str, Any] = {}
                for col_idx, col_name in enumerate(headers):
                    val = row[col_idx] if col_idx < len(row) else None
                    row_dict[col_name] = cls._format_cell_value(val)
                rows.append(row_dict)

            if not rows:
                raise DataSourceValidationError(
                    _("Лист «%(sheet)s» содержит заголовки, но не содержит строк данных.")
                    % {"sheet": used_sheet}
                )

            return headers, rows, used_sheet
        finally:
            wb.close()

    @classmethod
    def _format_cell_value(cls, val: Any) -> str:
        """Formats cell value to a clean string representation."""
        if val is None:
            return ""
        if isinstance(val, (datetime.datetime, datetime.date)):
            if isinstance(val, datetime.datetime) and (val.hour or val.minute or val.second):
                return val.strftime("%Y-%m-%d %H:%M:%S")
            return val.strftime("%Y-%m-%d")
        if isinstance(val, float):
            if val.is_integer():
                return str(int(val))
            return str(val)
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val).strip()


class DataSourceParserService:
    """Facade service for parsing tabular files, preserving backwards compatibility."""

    @classmethod
    def parse_csv_stream(cls, stream: io.StringIO) -> tuple[list[str], int]:
        """Parses CSV stream, returns (headers, total_rows)."""
        headers, rows = CsvImportService.parse_stream(stream)
        return headers, len(rows)

    @classmethod
    def parse_xlsx_file(cls, file_path: str) -> tuple[list[str], int]:
        """Parses XLSX file, returns (headers, total_rows)."""
        headers, rows, _sheet = XlsxImportService.parse_file(file_path)
        return headers, len(rows)


class DataSourceService:
    """Orchestrates ingestion, persistence, retrieval, and deletion of DataSources."""

    @classmethod
    def create_data_source(
        cls,
        name: str,
        uploaded_file: Any,
        user: Any | None = None,
        sheet_name: str | None = None,
        description: str = "",
    ) -> DataSource:
        """Validates, parses, and persists a DataSource along with its DataRecords."""
        detected_format = DataSourceSecurityValidator.validate_file(uploaded_file)

        # 1. Create model instance in PENDING status
        with transaction.atomic():
            data_source = DataSource.objects.create(
                name=name,
                file=uploaded_file,
                format=detected_format,
                status=DataSourceStatus.PROCESSING,
                sheet_name=sheet_name or "",
                description=description,
                uploaded_by=user if (user and getattr(user, "is_authenticated", False)) else None,
            )

        # 2. Parse file content
        try:
            if detected_format == DataSourceFormat.CSV:
                uploaded_file.seek(0)
                raw_bytes = uploaded_file.read()
                decoded_text = CsvImportService.detect_encoding_and_decode(raw_bytes)
                text_stream = io.StringIO(decoded_text)
                headers, rows = CsvImportService.parse_stream(text_stream)
                used_sheet = ""
            else:
                uploaded_file.seek(0)
                headers, rows, used_sheet = XlsxImportService.parse_file(
                    uploaded_file, sheet_name=sheet_name
                )

            # 3. Persist records and update status inside transaction
            with transaction.atomic():
                records_to_create = [
                    DataRecord(
                        data_source=data_source,
                        row_number=idx,
                        data=row_data,
                    )
                    for idx, row_data in enumerate(rows, start=1)
                ]
                DataRecord.objects.bulk_create(records_to_create, batch_size=1000)

                data_source.headers = headers
                data_source.row_count = len(records_to_create)
                data_source.column_count = len(headers)
                data_source.sheet_name = used_sheet or data_source.sheet_name
                data_source.status = DataSourceStatus.READY
                data_source.error_message = ""
                data_source.save(
                    update_fields=[
                        "headers",
                        "row_count",
                        "column_count",
                        "sheet_name",
                        "status",
                        "error_message",
                        "updated_at",
                    ]
                )

            AuditService.log(
                action="DATA_SOURCE_IMPORTED",
                resource_type="DataSource",
                resource_id=str(data_source.id),
                user=user,
                details={
                    "name": data_source.name,
                    "format": data_source.format,
                    "rows": data_source.row_count,
                    "columns": data_source.column_count,
                    "sheet": data_source.sheet_name,
                },
            )
            return data_source

        except Exception as err:
            data_source.status = DataSourceStatus.ERROR
            data_source.error_message = str(err)
            data_source.save(update_fields=["status", "error_message", "updated_at"])

            AuditService.log(
                action="DATA_SOURCE_IMPORT_FAILED",
                resource_type="DataSource",
                resource_id=str(data_source.id),
                user=user,
                details={"name": data_source.name, "error": str(err)},
            )
            if isinstance(err, DataSourceValidationError):
                raise
            raise DataSourceImportError(
                _("Сбой при обработке набора данных: %(msg)s") % {"msg": str(err)}
            ) from err

    @classmethod
    def delete_data_source(cls, data_source_id: int, user: Any | None = None) -> bool:
        """Deletes a DataSource, cascades its records, and removes the file from disk."""
        data_source = DataSource.objects.filter(pk=data_source_id).first()
        if not data_source:
            return False

        file_path = None
        if data_source.file:
            try:
                file_path = data_source.file.path
            except Exception:
                file_path = None

        name = data_source.name
        rows = data_source.row_count

        with transaction.atomic():
            data_source.delete()

        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        AuditService.log(
            action="DATA_SOURCE_DELETED",
            resource_type="DataSource",
            resource_id=str(data_source_id),
            user=user,
            details={"name": name, "rows_deleted": rows},
        )
        return True

    @classmethod
    def get_paginated_records(
        cls,
        data_source: DataSource,
        page_number: int = 1,
        page_size: int = 25,
    ) -> Page:
        """Returns paginated DataRecord query for previewing tabular records."""
        queryset = data_source.records.all().order_by("row_number")
        paginator = Paginator(queryset, page_size)
        return paginator.get_page(page_number)

    @classmethod
    def get_preview_records(
        cls,
        data_source: DataSource,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Returns the first N rows for quick summary display."""
        records = data_source.records.all().order_by("row_number")[:limit]
        return [r.data for r in records]

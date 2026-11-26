"""Bounded ZIP archive and XML security validator for OpenXML (DOCX / XLSX) files."""

import io
import os
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils.translation import gettext_lazy as _
from lxml import etree

ZIP_MAGIC_HEADER = b"PK\x03\x04"
STREAM_CHUNK_SIZE = 64 * 1024  # 64 KiB
DEFAULT_MAX_ZIP_ENTRIES = 500
DEFAULT_MAX_XML_DEPTH = 128

DANGEROUS_ARCHIVE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".sh",
        ".bin",
        ".msi",
        ".jar",
        ".ps1",
        ".py",
        ".dll",
        ".so",
        ".scr",
        ".pif",
        ".com",
        ".zip",
        ".7z",
        ".rar",
        ".gz",
        ".tar",
    }
)

XML_ENTRY_EXTENSIONS: frozenset[str] = frozenset({".xml", ".rels"})
FORBIDDEN_XML_DECLARATIONS_RE = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
FORBIDDEN_XML_UTF16_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


class _DepthCheckingSaxTarget:
    """Zero-DOM SAX target enforcing maximum XML nesting depth with O(depth) memory."""

    def __init__(self, max_depth: int) -> None:
        self.depth = 0
        self.max_depth = max_depth

    def start(self, _tag: str, _attrib: dict[str, str]) -> None:
        self.depth += 1
        if self.depth > self.max_depth:
            raise ValueError("Maximum XML nesting depth exceeded")

    def end(self, _tag: str) -> None:
        if self.depth > 0:
            self.depth -= 1

    def data(self, _data: str) -> None:
        pass

    def comment(self, _text: str) -> None:
        pass

    def close(self) -> None:
        pass


def get_actual_stream_size(file_obj: Any) -> int:
    """Measures the real byte length of a seekable stream or file on disk."""
    if isinstance(file_obj, (str, os.PathLike)):
        return os.path.getsize(file_obj)
    if hasattr(file_obj, "seek") and hasattr(file_obj, "tell"):
        pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = int(file_obj.tell())
        file_obj.seek(pos)
        return size
    return int(getattr(file_obj, "size", 0) or 0)


def _is_unsafe_zip_entry_name(name: str) -> bool:
    """Detects path traversal, absolute paths, backslashes, or control chars in ZIP names."""
    if not name or "\x00" in name or "\\" in name:
        return True
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        return True
    parts = [part for part in name.split("/") if part]
    return any(part in (".", "..") for part in parts)


def _contains_forbidden_xml_declarations(header_sample: bytes) -> bool:
    """Checks XML header bytes (UTF-8/ASCII or UTF-16) for DOCTYPE or ENTITY declarations."""
    if FORBIDDEN_XML_DECLARATIONS_RE.search(header_sample):
        return True
    if b"\x00" in header_sample[:64]:
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                decoded = header_sample.decode(encoding, errors="ignore")
                if FORBIDDEN_XML_UTF16_RE.search(decoded):
                    return True
            except Exception:
                continue
    return False


def _open_zip_buffer(file_obj: Any, actual_size: int, max_file_size: int) -> io.BytesIO:
    """Reads up to max_file_size bytes from file_obj into a bounded in-memory buffer."""
    if isinstance(file_obj, (str, os.PathLike)):
        if actual_size > max_file_size:
            raise ValueError("File exceeds maximum permitted size")
        with open(file_obj, "rb") as fh:
            data = fh.read(max_file_size + 1)
    elif hasattr(file_obj, "seek") and hasattr(file_obj, "read"):
        initial_pos = file_obj.tell()
        file_obj.seek(0)
        data = file_obj.read(max_file_size + 1)
        file_obj.seek(initial_pos)
    else:
        raise ValueError("Unsupported file source")

    if len(data) > max_file_size:
        raise ValueError("File exceeds maximum permitted size")
    return io.BytesIO(data)


def validate_ooxml_archive(
    file_obj: Any,
    *,
    max_file_size: int,
    max_uncompressed_size: int,
    max_entry_uncompressed_size: int,
    max_decompression_ratio: float,
    max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
    max_xml_depth: int = DEFAULT_MAX_XML_DEPTH,
    structure_validator: Callable[[list[str]], None] | None = None,
    error_cls: type[Exception] = ValueError,
    invalid_magic_message: str | None = None,
    invalid_zip_message: str | None = None,
) -> None:
    """Validates an OOXML ZIP archive without trusting ZIP metadata or unboundedly inflating.

    Guarantees:
    1. Enforces real file size limits before reading.
    2. Verifies PK\\x03\\x04 magic signature and ZIP container validity.
    3. Enforces entry count, unique entry names, non-encrypted entries, safe archive paths,
       and prohibited file extension checks BEFORE reading any compressed stream.
    4. Runs an OOXML structure validator (e.g. requiring word/document.xml or xl/workbook).
    5. Decompresses every entry via bounded 64 KiB streaming reads, measuring actual output
       bytes, per-entry and total decompression ratios, and validating XML/rels entries
       with DTD/entity declarations disabled and bounded XML nesting depth.
    """
    actual_size = get_actual_stream_size(file_obj)
    declared_size = getattr(file_obj, "size", None)
    effective_size = max(actual_size, int(declared_size or 0))

    if effective_size == 0:
        raise error_cls(_("Загруженный файл пуст."))

    if effective_size > max_file_size:
        max_mb = max_file_size // (1024 * 1024)
        raise error_cls(
            _("Размер файла превышает максимально допустимый лимит (%(max_mb)d МБ).")
            % {"max_mb": max_mb}
        )

    try:
        buf = _open_zip_buffer(file_obj, actual_size, max_file_size)
    except ValueError as exc:
        raise error_cls(
            _("Размер файла превышает максимально допустимый лимит (%(max_mb)d МБ).")
            % {"max_mb": max_file_size // (1024 * 1024)}
        ) from exc

    magic = buf.read(4)
    buf.seek(0)
    if magic != ZIP_MAGIC_HEADER:
        raise error_cls(
            invalid_magic_message
            or _("Файл не является корректным документом (неверная сигнатура ZIP).")
        )

    if not zipfile.is_zipfile(buf):
        raise error_cls(
            invalid_zip_message or _("Файл повреждён или не является валидным ZIP-архивом.")
        )
    buf.seek(0)

    try:
        with zipfile.ZipFile(buf, "r") as archive:
            infolist = archive.infolist()
            if not infolist:
                raise error_cls(_("ZIP-архив документа пуст."))
            if len(infolist) > max_entries:
                raise error_cls(
                    _("Количество элементов в архиве превышает допустимый лимит безопасности.")
                )

            namelist: list[str] = []
            seen_names: set[str] = set()
            declared_total = 0

            for info in infolist:
                if info.flag_bits & 0x1:
                    raise error_cls(_("Зашифрованные архивы не поддерживаются."))

                if _is_unsafe_zip_entry_name(info.filename):
                    raise error_cls(_("Архив содержит недопустимый путь элемента."))

                if info.filename in seen_names:
                    raise error_cls(_("Архив содержит дублирующиеся элементы."))
                seen_names.add(info.filename)
                namelist.append(info.filename)

                _root, entry_ext = os.path.splitext(info.filename)
                if entry_ext.lower() in DANGEROUS_ARCHIVE_EXTENSIONS:
                    raise error_cls(
                        _("В архиве обнаружен недопустимый файл '%(name)s'.")
                        % {"name": info.filename}
                    )

                if info.file_size > max_entry_uncompressed_size:
                    raise error_cls(
                        _("Размер элемента архива превышает допустимый лимит безопасности.")
                    )

                declared_total += info.file_size
                if declared_total > max_uncompressed_size:
                    raise error_cls(
                        _("Общий распакованный объём документа превышает лимит безопасности.")
                    )

            if declared_total / max(actual_size, 1) > max_decompression_ratio:
                raise error_cls(_("Обнаружен аномальный коэффициент сжатия (возможная zip-бомба)."))

            if structure_validator is not None:
                structure_validator(namelist)

            # Bounded streaming decompression: never trust ZIP headers alone.
            actual_total_bytes = 0
            for info in infolist:
                if info.is_dir():
                    continue

                entry_bytes = 0
                is_xml_entry = os.path.splitext(info.filename)[1].lower() in XML_ENTRY_EXTENSIONS
                xml_parser = (
                    etree.XMLParser(
                        target=_DepthCheckingSaxTarget(max_xml_depth),
                        resolve_entities=False,
                        no_network=True,
                        dtd_validation=False,
                        load_dtd=False,
                        huge_tree=False,
                    )
                    if is_xml_entry
                    else None
                )
                xml_header_tail = b""

                with archive.open(info, "r") as entry_stream:
                    while True:
                        chunk = entry_stream.read(STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        chunk_len = len(chunk)
                        entry_bytes += chunk_len
                        actual_total_bytes += chunk_len

                        if entry_bytes > max_entry_uncompressed_size:
                            raise error_cls(
                                _("Реальный размер элемента архива превышает лимит безопасности.")
                            )
                        if actual_total_bytes > max_uncompressed_size:
                            raise error_cls(
                                _(
                                    "Общий распакованный объём документа превышает лимит безопасности."
                                )
                            )
                        if actual_total_bytes / max(actual_size, 1) > max_decompression_ratio:
                            raise error_cls(
                                _("Обнаружен аномальный коэффициент сжатия (возможная zip-бомба).")
                            )
                        if (
                            entry_bytes > 512 * 1024
                            and entry_bytes / max(info.compress_size, 1) > max_decompression_ratio
                        ):
                            raise error_cls(
                                _(
                                    "Обнаружен аномальный коэффициент сжатия элемента (возможная zip-бомба)."
                                )
                            )

                        if xml_parser is not None:
                            window = xml_header_tail + chunk
                            if _contains_forbidden_xml_declarations(window):
                                raise error_cls(
                                    _(
                                        "XML-содержимое документа содержит запрещённые объявления DOCTYPE или ENTITY."
                                    )
                                )
                            xml_header_tail = window[-64:]
                            try:
                                xml_parser.feed(chunk)
                            except (etree.XMLSyntaxError, ValueError) as exc:
                                raise error_cls(
                                    _(
                                        "Документ содержит некорректную или небезопасную XML-разметку."
                                    )
                                ) from exc

                if xml_parser is not None:
                    try:
                        xml_parser.close()
                    except (etree.XMLSyntaxError, ValueError) as exc:
                        raise error_cls(
                            _("Документ содержит некорректную или небезопасную XML-разметку.")
                        ) from exc

    except error_cls:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, RuntimeError) as exc:
        raise error_cls(
            invalid_zip_message or _("Файл повреждён или не является валидным ZIP-архивом.")
        ) from exc


def validate_docx_structure(namelist: list[str]) -> None:
    """Ensures DOCX OpenXML archive contains word/document.xml."""
    if "word/document.xml" not in namelist:
        raise ValueError(
            _("Файл не является документом Word DOCX: отсутствует компонент word/document.xml.")
        )


def validate_xlsx_structure(namelist: list[str]) -> None:
    """Ensures XLSX OpenXML archive contains workbook metadata."""
    has_workbook = any(name.startswith("xl/workbook") for name in namelist)
    has_content_types = "[Content_Types].xml" in namelist
    if not (has_workbook or has_content_types):
        raise ValueError(_("Архив XLSX не содержит структуры рабочей книги Excel."))


def validate_docx_archive(
    file_obj: Any,
    *,
    max_file_size: int,
    max_uncompressed_size: int = 50 * 1024 * 1024,
    max_entry_uncompressed_size: int = 20 * 1024 * 1024,
    max_decompression_ratio: float = 100.0,
    error_cls: type[Exception] = ValueError,
) -> None:
    """Runs strict bounded archive and XML validation for DOCX files."""

    def _docx_structure(namelist: list[str]) -> None:
        if "word/document.xml" not in namelist:
            raise error_cls(
                _("Файл не является документом Word DOCX: отсутствует компонент word/document.xml.")
            )

    validate_ooxml_archive(
        file_obj,
        max_file_size=max_file_size,
        max_uncompressed_size=max_uncompressed_size,
        max_entry_uncompressed_size=max_entry_uncompressed_size,
        max_decompression_ratio=max_decompression_ratio,
        structure_validator=_docx_structure,
        error_cls=error_cls,
        invalid_magic_message=_(
            "Файл не является корректным DOCX-документом (неверная сигнатура ZIP)."
        ),
        invalid_zip_message=_("Файл повреждён или не является валидным ZIP-архивом."),
    )


def validate_xlsx_archive(
    file_obj: Any,
    *,
    max_file_size: int,
    max_uncompressed_size: int = 100 * 1024 * 1024,
    max_entry_uncompressed_size: int = 50 * 1024 * 1024,
    max_decompression_ratio: float = 100.0,
    error_cls: type[Exception] = ValueError,
) -> None:
    """Runs strict bounded archive and XML validation for XLSX files."""

    def _xlsx_structure(namelist: list[str]) -> None:
        has_workbook = any(name.startswith("xl/workbook") for name in namelist)
        has_content_types = "[Content_Types].xml" in namelist
        if not (has_workbook or has_content_types):
            raise error_cls(_("Архив XLSX не содержит структуры рабочей книги Excel."))

    validate_ooxml_archive(
        file_obj,
        max_file_size=max_file_size,
        max_uncompressed_size=max_uncompressed_size,
        max_entry_uncompressed_size=max_entry_uncompressed_size,
        max_decompression_ratio=max_decompression_ratio,
        structure_validator=_xlsx_structure,
        error_cls=error_cls,
        invalid_magic_message=_("Файл не является корректным архивом Excel SpreadsheetML (.xlsx)."),
        invalid_zip_message=_("Файл повреждён или не является валидным ZIP-контейнером."),
    )


def build_safe_file_response(
    file_field: Any,
    download_name: str,
    *,
    content_type: str | None = None,
    not_found_message: str = _("Файл не найден на сервере."),
) -> FileResponse:
    """Serves a stored FileField strictly within MEDIA_ROOT with nosniff header."""
    if not file_field:
        raise Http404(not_found_message)

    try:
        raw_path = file_field.path
    except Exception as exc:
        raise Http404(not_found_message) from exc

    media_root = Path(settings.MEDIA_ROOT).resolve()
    resolved_path = Path(raw_path).resolve()
    if not resolved_path.is_relative_to(media_root) or not resolved_path.is_file():
        raise Http404(not_found_message)

    safe_filename = os.path.basename(download_name) or "download"
    response_kwargs: dict[str, Any] = {
        "as_attachment": True,
        "filename": safe_filename,
    }
    if content_type:
        response_kwargs["content_type"] = content_type

    response = FileResponse(open(resolved_path, "rb"), **response_kwargs)
    response["X-Content-Type-Options"] = "nosniff"
    return response

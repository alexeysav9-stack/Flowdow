"""Tests for DataSource file security, extension checks, and archive integrity."""

import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.data_sources.constants import MAX_DATA_SOURCE_FILE_SIZE
from apps.data_sources.services import DataSourceSecurityValidator, DataSourceValidationError


def test_reject_wrong_extension():
    """Verifies that non-CSV/XLSX files are rejected."""
    bad_file = SimpleUploadedFile("data.pdf", b"%PDF-1.4...", content_type="application/pdf")
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(bad_file)
    assert "Неподдерживаемый формат" in str(exc.value)


def test_reject_empty_file():
    """Verifies that 0-byte files are rejected."""
    empty_file = SimpleUploadedFile("data.csv", b"", content_type="text/csv")
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(empty_file)
    assert "файл пуст" in str(exc.value)


def test_reject_binary_csv():
    """Verifies that binary files with null bytes are rejected as CSV."""
    binary_content = b"header1,header2\x00\x01\x02binarydata"
    bad_file = SimpleUploadedFile("data.csv", binary_content, content_type="text/csv")
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(bad_file)
    assert "бинарные нулевые байты" in str(exc.value)


def test_reject_corrupted_xlsx_zip():
    """Verifies that corrupted ZIP files with .xlsx extension are rejected."""
    bad_file = SimpleUploadedFile(
        "corrupted.xlsx",
        b"PK\x03\x04corrupteddataandheaders",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(bad_file)
    assert "повреждён или не является валидным ZIP-контейнером" in str(exc.value)


def test_reject_xlsx_missing_workbook_structure():
    """Verifies rejection of ZIP files lacking Excel OpenXML structures."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("some_text.txt", "Hello world")
    buf.seek(0)

    fake_xlsx = SimpleUploadedFile(
        "fake.xlsx",
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(fake_xlsx)
    assert "не содержит структуры рабочей книги Excel" in str(exc.value)


def test_reject_xlsx_with_executable_payload():
    """Verifies rejection of XLSX archives containing malicious executables."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("xl/workbook.xml", "<workbook></workbook>")
        zf.writestr("xl/malware.exe", b"MZ\x90\x00fake_binary")
    buf.seek(0)

    evil_xlsx = SimpleUploadedFile(
        "evil.xlsx",
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(evil_xlsx)
    assert "обнаружен недопустимый файл" in str(exc.value)


def test_reject_oversized_file():
    """Verifies rejection of files exceeding the 20 MB size limit."""
    oversized_file = SimpleUploadedFile("big.csv", b"dummy", content_type="text/csv")
    oversized_file.size = MAX_DATA_SOURCE_FILE_SIZE + 1024

    with pytest.raises(DataSourceValidationError) as exc:
        DataSourceSecurityValidator.validate_file(oversized_file)
    assert "превышает допустимый предел" in str(exc.value)

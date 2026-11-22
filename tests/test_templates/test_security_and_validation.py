"""Tests for template upload security, file validation, and path traversal protection."""

import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.templates_manager.services import (
    DocxSecurityValidator,
    TemplateValidationError,
)


def test_reject_wrong_file_extension():
    """Verifies rejection of non-docx extensions (e.g. .pdf, .exe)."""
    file_obj = SimpleUploadedFile("contract.pdf", b"PDF dummy content")
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="contract.pdf")
    assert "Разрешены только файлы .docx" in str(exc.value)


def test_reject_invalid_magic_bytes():
    """Verifies rejection when file has .docx extension but lacks ZIP PK magic header."""
    file_obj = SimpleUploadedFile("fake.docx", b"This is plain text pretending to be docx.")
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="fake.docx")
    assert "неверная сигнатура ZIP" in str(exc.value)


def test_reject_corrupted_zip_archive():
    """Verifies rejection of truncated or corrupted ZIP archives."""
    corrupted_bytes = b"PK\x03\x04\x00\x00\x00\x00\x00\x00corrupted_payload"
    file_obj = SimpleUploadedFile("corrupted.docx", corrupted_bytes)
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="corrupted.docx")
    assert "не является валидным ZIP-архивом" in str(exc.value)


def test_reject_zip_missing_document_xml():
    """Verifies rejection when valid zip container lacks word/document.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("some_folder/notes.txt", "Some text file")
    buf.seek(0)

    file_obj = SimpleUploadedFile("missing_xml.docx", buf.getvalue())
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="missing_xml.docx")
    assert "отсутствует компонент word/document.xml" in str(exc.value)


def test_reject_zip_with_executable_payload():
    """Verifies rejection when archive contains dangerous executable files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("payload.exe", b"binary executable content")
    buf.seek(0)

    file_obj = SimpleUploadedFile("malicious.docx", buf.getvalue())
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="malicious.docx")
    assert "недопустимый файл 'payload.exe'" in str(exc.value)


def test_reject_oversized_file(monkeypatch):
    """Verifies rejection of files exceeding maximum size limit."""
    from apps.templates_manager import services

    monkeypatch.setattr(services, "MAX_TEMPLATE_FILE_SIZE", 100)  # 100 bytes limit for test
    oversized_bytes = b"PK\x03\x04" + b"A" * 200
    file_obj = SimpleUploadedFile("large.docx", oversized_bytes)
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(file_obj, filename="large.docx")
    assert "превышает максимально допустимый лимит" in str(exc.value)


def test_reject_empty_file():
    """Verifies rejection of 0-byte file."""
    empty_file = SimpleUploadedFile("empty.docx", b"")
    with pytest.raises(TemplateValidationError) as exc:
        DocxSecurityValidator.validate_file(empty_file, filename="empty.docx")
    assert "Загруженный файл пуст" in str(exc.value)

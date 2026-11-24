"""Tests for DOCX inspection and variable discovery engine."""

import io

import pytest

from apps.templates_manager.services import (
    TemplateInspectionService,
    TemplateValidationError,
)
from tests.conftest import make_docx_bytes


def test_inspect_valid_docx_with_variables():
    """Verifies extracting simple placeholder variables from synthetic DOCX."""
    docx_bytes = make_docx_bytes(
        [
            "Договор об обучении студента {{ full_name }}.",
            "Группа: {{ group }}, Специальность: {{ specialty }}.",
            "Дата выдачи диплома: {{ issue_date }}.",
        ]
    )
    buf = io.BytesIO(docx_bytes)
    variables = TemplateInspectionService.inspect_file(buf, filename="student.docx")
    assert variables == ["full_name", "group", "issue_date", "specialty"]


def test_inspect_docx_with_split_xml_runs():
    """Verifies that variables split across multiple Word XML runs are correctly unified and detected.

    Simulates Word's internal fragmentations where '{{' is in run 1, ' full_name ' in run 2, and '}}' in run 3.
    """
    docx_bytes = make_docx_bytes(
        [
            # Split run paragraph 1: {{ full_name }}
            ["{{", " full_name ", "}}"],
            # Split run paragraph 2: Group: {{ group }}
            ["Группа: ", "{{", "group", "}}"],
            # Split run paragraph 3: {{ specialty }} and {{ issue_date }}
            ["Специальность: {{", "specialty", "}} от {{ ", "issue_date", " }}"],
        ]
    )
    buf = io.BytesIO(docx_bytes)
    variables = TemplateInspectionService.inspect_file(buf, filename="split_runs.docx")
    assert variables == ["full_name", "group", "issue_date", "specialty"]


def test_inspect_docx_with_no_variables():
    """Verifies that a valid DOCX with plain text and no variables returns an empty list."""
    docx_bytes = make_docx_bytes(
        [
            "Обычный статический текст документа без каких-либо плейсхолдеров.",
            "Компания обязуется выполнить работы в установленный срок.",
        ]
    )
    buf = io.BytesIO(docx_bytes)
    variables = TemplateInspectionService.inspect_file(buf, filename="static.docx")
    assert variables == []


def test_inspect_docx_filters_unsupported_or_malicious_constructs():
    """Verifies that non-identifier tokens, built-ins, or dunder names are rejected."""
    docx_bytes = make_docx_bytes(
        [
            "Валидные: {{ employee_name }} и {{ salary }}.",
            "Двойные подчеркивания: {{ __class__ }}.",
        ]
    )
    buf = io.BytesIO(docx_bytes)
    with pytest.raises(TemplateValidationError):
        TemplateInspectionService.inspect_file(buf, filename="filter_test.docx")


def test_text_regex_inspection_fallback():
    """Verifies fallback regex-based extractor for text strings."""
    text = "Agreement with {{ company }} on {{ signing_date | format_date }}."
    vars_found = TemplateInspectionService.extract_variables_from_text(text)
    assert vars_found == ["company", "signing_date"]


def test_inspect_docx_with_cyrillic_variables():
    """Verifies that Cyrillic template variables (e.g. {{ фио }}, {{ должность }}) are detected."""
    docx_bytes = make_docx_bytes(
        [
            "Договор с сотрудником: {{ фио }}.",
            "Должность: {{ должность }}, оклад: {{ оклад_руб }}.",
        ]
    )
    buf = io.BytesIO(docx_bytes)
    variables = TemplateInspectionService.inspect_file(buf, filename="cyrillic.docx")
    assert variables == ["должность", "оклад_руб", "фио"]


def test_text_regex_inspection_cyrillic():
    """Verifies fallback regex extractor with Cyrillic variables."""
    text = "Справка выдана {{ фио }} на должность {{ должность }}."
    vars_found = TemplateInspectionService.extract_variables_from_text(text)
    assert vars_found == ["должность", "фио"]

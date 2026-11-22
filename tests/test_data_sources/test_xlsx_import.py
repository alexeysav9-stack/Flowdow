"""Tests for XLSX Excel workbook parsing and sheet selection."""

import datetime
import io

import pytest

from apps.data_sources.services import DataSourceValidationError, XlsxImportService
from tests.conftest import make_xlsx_bytes


def test_xlsx_import_basic():
    """Verifies that basic XLSX file is correctly parsed."""
    data = {
        "Sheet1": [
            ["ФИО", "Группа", "Специальность"],
            ["Иванов Иван", "ИСИП-21", "Разработка ПО"],
            ["Петров Петр", "ИСИП-22", "Сетевое администрирование"],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    headers, rows, sheet_used = XlsxImportService.parse_file(file_obj)
    assert headers == ["ФИО", "Группа", "Специальность"]
    assert len(rows) == 2
    assert sheet_used == "Sheet1"
    assert rows[0]["ФИО"] == "Иванов Иван"
    assert rows[1]["Группа"] == "ИСИП-22"


def test_xlsx_multiple_sheets_and_sheet_selection():
    """Verifies inspection of sheet names and explicit sheet selection."""
    data = {
        "Students": [
            ["ФИО", "Курс"],
            ["Смирнов", 2],
        ],
        "Teachers": [
            ["Преподаватель", "Кафедра"],
            ["Ковалев", "Информатика"],
        ],
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    sheet_names = XlsxImportService.get_sheet_names(file_obj)
    assert sheet_names == ["Students", "Teachers"]

    # Read specific sheet "Teachers"
    file_obj.seek(0)
    headers, rows, sheet_used = XlsxImportService.parse_file(file_obj, sheet_name="Teachers")
    assert sheet_used == "Teachers"
    assert headers == ["Преподаватель", "Кафедра"]
    assert len(rows) == 1
    assert rows[0]["Преподаватель"] == "Ковалев"


def test_xlsx_cell_value_formatting():
    """Verifies clean conversion of dates, datetimes, numbers, and booleans."""
    test_date = datetime.date(2024, 9, 1)
    test_datetime = datetime.datetime(2024, 9, 1, 14, 30, 0)
    data = {
        "Sheet1": [
            ["Имя", "Оклад", "Коэффициент", "Активен", "Дата_приёма", "Время_события", "Пусто"],
            ["Иван", 150000, 1.25, True, test_date, test_datetime, None],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    headers, rows, _sheet = XlsxImportService.parse_file(file_obj)
    row = rows[0]
    assert row["Имя"] == "Иван"
    assert row["Оклад"] == "150000"
    assert row["Коэффициент"] == "1.25"
    assert row["Активен"] == "true"
    assert row["Дата_приёма"] == "2024-09-01"
    assert row["Время_события"] == "2024-09-01 14:30:00"
    assert row["Пусто"] == ""


def test_xlsx_reject_duplicate_headers():
    """Verifies rejection of XLSX sheet with duplicate headers."""
    data = {
        "Sheet1": [
            ["ФИО", "Оклад", "ФИО"],
            ["Иванов", 100000, "Иван"],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    with pytest.raises(DataSourceValidationError) as exc:
        XlsxImportService.parse_file(file_obj)
    assert "повторяющиеся заголовки" in str(exc.value)


def test_xlsx_reject_empty_header():
    """Verifies rejection of XLSX sheet with empty header column."""
    data = {
        "Sheet1": [
            ["ФИО", None, "Оклад"],
            ["Иванов", "инженер", 100000],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    with pytest.raises(DataSourceValidationError) as exc:
        XlsxImportService.parse_file(file_obj)
    assert "имеет пустой заголовок" in str(exc.value)


def test_xlsx_skips_empty_rows():
    """Verifies that empty rows in XLSX are ignored."""
    data = {
        "Sheet1": [
            [None, None],
            ["ФИО", "Оклад"],
            [None, None],
            ["Иванов", 100000],
            ["", ""],
            ["Петров", 90000],
            [None, None],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    headers, rows, _sheet = XlsxImportService.parse_file(file_obj)
    assert headers == ["ФИО", "Оклад"]
    assert len(rows) == 2
    assert rows[0]["ФИО"] == "Иванов"
    assert rows[1]["ФИО"] == "Петров"


def test_xlsx_reject_empty_sheet():
    """Verifies rejection when target sheet contains no data."""
    data = {
        "Sheet1": [
            [None, None],
            ["", ""],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    with pytest.raises(DataSourceValidationError) as exc:
        XlsxImportService.parse_file(file_obj)
    assert "пуст или не содержит данных" in str(exc.value)


def test_xlsx_reject_header_only_sheet():
    """Verifies rejection when sheet contains headers but no data rows."""
    data = {
        "Sheet1": [
            ["Колонка1", "Колонка2"],
        ]
    }
    file_bytes = make_xlsx_bytes(data)
    file_obj = io.BytesIO(file_bytes)

    with pytest.raises(DataSourceValidationError) as exc:
        XlsxImportService.parse_file(file_obj)
    assert "не содержит строк данных" in str(exc.value)


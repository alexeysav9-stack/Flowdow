"""Tests for CSV parsing, encoding handling, and delimiter detection."""

import io

import pytest

from apps.data_sources.services import CsvImportService, DataSourceValidationError
from tests.conftest import make_csv_bytes


def test_csv_import_utf8_standard():
    """Verifies that standard UTF-8 CSV is parsed accurately."""
    rows = [
        ["ФИО", "Группа", "Специальность"],
        ["Иванов Иван Иванович", "ИСИП-21", "Разработка ПО"],
        ["Петров Петр Петрович", "ИСИП-22", "Сетевое администрирование"],
    ]
    raw_bytes = make_csv_bytes(rows, delimiter=",", encoding="utf-8")
    text = CsvImportService.detect_encoding_and_decode(raw_bytes)
    stream = io.StringIO(text)
    headers, parsed_rows = CsvImportService.parse_stream(stream)

    assert headers == ["ФИО", "Группа", "Специальность"]
    assert len(parsed_rows) == 2
    assert parsed_rows[0]["ФИО"] == "Иванов Иван Иванович"
    assert parsed_rows[0]["Группа"] == "ИСИП-21"
    assert parsed_rows[1]["Специальность"] == "Сетевое администрирование"


def test_csv_import_utf8_with_bom():
    """Verifies that UTF-8 with BOM (\xef\xbb\xbf) is stripped cleanly without garbling headers."""
    rows = [
        ["ФИО", "Оклад"],
        ["Сидорова Анна", "120000"],
    ]
    raw_bytes = make_csv_bytes(rows, delimiter=",", encoding="utf-8-sig")
    assert raw_bytes.startswith(b"\xef\xbb\xbf")

    text = CsvImportService.detect_encoding_and_decode(raw_bytes)
    stream = io.StringIO(text)
    headers, parsed_rows = CsvImportService.parse_stream(stream)

    assert headers == ["ФИО", "Оклад"]
    assert not headers[0].startswith("\ufeff")
    assert len(parsed_rows) == 1
    assert parsed_rows[0]["ФИО"] == "Сидорова Анна"


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_csv_delimiter_autodetection(delimiter: str):
    """Verifies automatic detection of common CSV delimiters."""
    rows = [
        ["Имя", "Возраст", "Город"],
        ["Алексей", "30", "Москва"],
        ["Мария", "25", "Санкт-Петербург"],
    ]
    raw_bytes = make_csv_bytes(rows, delimiter=delimiter, encoding="utf-8")
    text = CsvImportService.detect_encoding_and_decode(raw_bytes)
    detected_delim = CsvImportService.detect_delimiter(text)
    assert detected_delim == delimiter

    stream = io.StringIO(text)
    headers, parsed_rows = CsvImportService.parse_stream(stream)
    assert headers == ["Имя", "Возраст", "Город"]
    assert len(parsed_rows) == 2
    assert parsed_rows[0]["Город"] == "Москва"


def test_csv_reject_duplicate_headers():
    """Verifies rejection of CSV files with duplicate column headers."""
    csv_text = "ФИО,Группа,ФИО\nИванов,ИС-21,Иван\n"
    stream = io.StringIO(csv_text)
    with pytest.raises(DataSourceValidationError) as exc:
        CsvImportService.parse_stream(stream)
    assert "повторяющиеся названия колонок" in str(exc.value)


def test_csv_reject_empty_column_header():
    """Verifies rejection of CSV files with empty header columns."""
    csv_text = "Имя,,Фамилия\nИван,Петрович,Иванов\n"
    stream = io.StringIO(csv_text)
    with pytest.raises(DataSourceValidationError) as exc:
        CsvImportService.parse_stream(stream)
    assert "пустой заголовок" in str(exc.value)


def test_csv_skips_blank_lines():
    """Verifies that empty lines before, during, and after data are ignored cleanly."""
    csv_text = "\n\nКолонка1,Колонка2\n\nЗначение1,Значение2\n   ,   \nЗначение3,Значение4\n\n\n"
    stream = io.StringIO(csv_text)
    headers, parsed_rows = CsvImportService.parse_stream(stream)
    assert headers == ["Колонка1", "Колонка2"]
    assert len(parsed_rows) == 2
    assert parsed_rows[0]["Колонка1"] == "Значение1"
    assert parsed_rows[1]["Колонка1"] == "Значение3"


def test_csv_reject_row_with_excess_columns():
    """Verifies detection of individual records containing more values than declared headers."""
    csv_text = "Колонка1,Колонка2\nЗначение1,Значение2,ЛишнееЗначение\n"
    stream = io.StringIO(csv_text)
    with pytest.raises(DataSourceValidationError) as exc:
        CsvImportService.parse_stream(stream)
    assert "содержит 3 колонок при ожидаемых 2" in str(exc.value)


def test_csv_pads_missing_columns():
    """Verifies that rows with fewer columns are safely padded with empty strings."""
    csv_text = "Колонка1,Колонка2,Колонка3\nЗначение1\n"
    stream = io.StringIO(csv_text)
    headers, parsed_rows = CsvImportService.parse_stream(stream)
    assert len(parsed_rows) == 1
    assert parsed_rows[0]["Колонка1"] == "Значение1"
    assert parsed_rows[0]["Колонка2"] == ""
    assert parsed_rows[0]["Колонка3"] == ""


def test_csv_reject_empty_file():
    """Verifies rejection of completely empty CSV file."""
    stream = io.StringIO("")
    with pytest.raises(DataSourceValidationError) as exc:
        CsvImportService.parse_stream(stream)
    assert "пуст или не содержит данных" in str(exc.value)


def test_csv_reject_header_only_file():
    """Verifies rejection of CSV with headers but no data rows."""
    stream = io.StringIO("Колонка1,Колонка2\n")
    with pytest.raises(DataSourceValidationError) as exc:
        CsvImportService.parse_stream(stream)
    assert "не содержит строк данных" in str(exc.value)

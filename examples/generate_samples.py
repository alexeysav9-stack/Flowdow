"""Script to generate synthetic demo files for Flowdow (RU and ENG)."""

import csv
import shutil
from pathlib import Path

import openpyxl
from docx import Document

EXAMPLES_DIR = Path(__file__).resolve().parent


def create_sample_docx_ru():
    """Generates Russian employment certificate template."""
    docx_path = EXAMPLES_DIR / "sample_certificate_ru.docx"
    doc = Document()
    doc.add_heading("СПРАВКА С МЕСТА РАБОТЫ (RU)", level=1)
    doc.add_paragraph(
        "Настоящим удостоверяется, что указанный сотрудник действительно работает в нашей организации:"
    )

    table = doc.add_table(rows=4, cols=2)
    rows = table.rows
    rows[0].cells[0].text = "ФИО сотрудника:"
    rows[0].cells[1].text = "{{ full_name }}"
    rows[1].cells[0].text = "Должность:"
    rows[1].cells[1].text = "{{ position }}"
    rows[2].cells[0].text = "Отдел:"
    rows[2].cells[1].text = "{{ department }}"
    rows[3].cells[0].text = "Оклад:"
    rows[3].cells[1].text = "{{ salary }}"

    doc.add_paragraph()
    doc.add_paragraph("Справка выдана по месту требования для официального предъявления.")
    doc.add_paragraph("Дата выдачи: {{ current_date }}")
    doc.add_paragraph("Подпись уполномоченного лица: _________________________")

    doc.save(str(docx_path))
    shutil.copyfile(docx_path, EXAMPLES_DIR / "sample_certificate.docx")
    print(f"Created: {docx_path}")


def create_sample_docx_eng():
    """Generates English employment certificate template."""
    for filename in ["sample_certificate_eng.docx", "sample_certificate_en.docx"]:
        docx_path = EXAMPLES_DIR / filename
        doc = Document()
        doc.add_heading("CERTIFICATE OF EMPLOYMENT (ENG)", level=1)
        doc.add_paragraph(
            "This is to certify that the following employee is currently employed with our organization:"
        )

        table = doc.add_table(rows=4, cols=2)
        rows = table.rows
        rows[0].cells[0].text = "Employee Name:"
        rows[0].cells[1].text = "{{ full_name }}"
        rows[1].cells[0].text = "Position:"
        rows[1].cells[1].text = "{{ position }}"
        rows[2].cells[0].text = "Department:"
        rows[2].cells[1].text = "{{ department }}"
        rows[3].cells[0].text = "Monthly Salary:"
        rows[3].cells[1].text = "{{ salary }}"

        doc.add_paragraph()
        doc.add_paragraph("This certificate is issued upon request for official purposes.")
        doc.add_paragraph("Issue Date: {{ current_date }}")
        doc.add_paragraph("Authorized Signature: _________________________")

        doc.save(str(docx_path))
        print(f"Created: {docx_path}")


def create_sample_csv_ru():
    """Generates Russian CSV employee dataset."""
    data = [
        ["ФИО", "Должность", "Отдел", "Оклад"],
        ["Иванов Иван Иванович", "Старший разработчик", "IT Департамент", "180 000 руб."],
        ["Петрова Анна Сергеевна", "Ведущий аналитик", "Финансовый отдел", "160 000 руб."],
        ["Сидоров Алексей Павлович", "Менеджер проектов", "Управление проектами", "150 000 руб."],
        ["Кузнецова Елена Дмитриевна", "HR-директор", "Управление персоналом", "190 000 руб."],
        ["Смирнов Михаил Васильевич", "Системный администратор", "Инфраструктура", "130 000 руб."],
    ]
    for filename in ["sample_employees_ru.csv", "sample_employees.csv"]:
        csv_path = EXAMPLES_DIR / filename
        with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Created: {csv_path}")


def create_sample_csv_eng():
    """Generates English CSV employee dataset."""
    data = [
        ["Full Name", "Position", "Department", "Salary"],
        ["John Doe", "Senior Software Engineer", "Engineering", "$9,500"],
        ["Jane Smith", "Lead Financial Analyst", "Finance", "$8,200"],
        ["Alex Johnson", "Project Manager", "Operations", "$7,800"],
        ["Emily Davis", "HR Director", "Human Resources", "$9,000"],
        ["Michael Brown", "DevOps Engineer", "Infrastructure", "$7,500"],
    ]
    for filename in ["sample_employees_eng.csv", "sample_employees_en.csv"]:
        csv_path = EXAMPLES_DIR / filename
        with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Created: {csv_path}")


def create_sample_xlsx_ru():
    """Generates Russian XLSX employee workbook."""
    data = [
        ["ФИО", "Должность", "Отдел", "Оклад"],
        ["Иванов Иван Иванович", "Старший разработчик", "IT Департамент", "180 000 руб."],
        ["Петрова Анна Сергеевна", "Ведущий аналитик", "Финансовый отдел", "160 000 руб."],
        ["Сидоров Алексей Павлович", "Менеджер проектов", "Управление проектами", "150 000 руб."],
        ["Кузнецова Елена Дмитриевна", "HR-директор", "Управление персоналом", "190 000 руб."],
        ["Смирнов Михаил Васильевич", "Системный администратор", "Инфраструктура", "130 000 руб."],
    ]
    for filename in ["sample_employees_ru.xlsx", "sample_employees.xlsx"]:
        xlsx_path = EXAMPLES_DIR / filename
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Сотрудники (RU)"
        for row in data:
            ws.append(row)
        wb.save(str(xlsx_path))
        print(f"Created: {xlsx_path}")


def create_sample_xlsx_eng():
    """Generates English XLSX employee workbook."""
    data = [
        ["Full Name", "Position", "Department", "Salary"],
        ["John Doe", "Senior Software Engineer", "Engineering", "$9,500"],
        ["Jane Smith", "Lead Financial Analyst", "Finance", "$8,200"],
        ["Alex Johnson", "Project Manager", "Operations", "$7,800"],
        ["Emily Davis", "HR Director", "Human Resources", "$9,000"],
        ["Michael Brown", "DevOps Engineer", "Infrastructure", "$7,500"],
    ]
    for filename in ["sample_employees_eng.xlsx", "sample_employees_en.xlsx"]:
        xlsx_path = EXAMPLES_DIR / filename
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Employees (ENG)"
        for row in data:
            ws.append(row)
        wb.save(str(xlsx_path))
        print(f"Created: {xlsx_path}")


if __name__ == "__main__":
    create_sample_docx_ru()
    create_sample_docx_eng()
    create_sample_csv_ru()
    create_sample_csv_eng()
    create_sample_xlsx_ru()
    create_sample_xlsx_eng()

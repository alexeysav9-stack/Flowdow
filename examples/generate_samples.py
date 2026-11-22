"""Script to generate synthetic demo files for Flowdow."""

import csv
from pathlib import Path

import openpyxl
from docx import Document

EXAMPLES_DIR = Path(__file__).resolve().parent


def create_sample_docx():
    docx_path = EXAMPLES_DIR / "sample_certificate.docx"
    doc = Document()
    doc.add_heading("CERTIFICATE OF EMPLOYMENT", level=1)
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


def create_sample_csv():
    csv_path = EXAMPLES_DIR / "sample_employees.csv"
    data = [
        ["ФИО", "Должность", "Отдел", "Оклад"],
        ["Иванов Иван Иванович", "Старший разработчик", "IT Департамент", "180 000 руб."],
        ["Петрова Анна Сергеевна", "Ведущий аналитик", "Финансовый отдел", "160 000 руб."],
        ["Сидоров Алексей Павлович", "Менеджер проектов", "Управление проектами", "150 000 руб."],
        ["Кузнецова Елена Дмитриевна", "HR-директор", "Управление персоналом", "190 000 руб."],
        ["Смирнов Михаил Васильевич", "Системный администратор", "Инфраструктура", "130 000 руб."],
    ]
    with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print(f"Created: {csv_path}")


def create_sample_xlsx():
    xlsx_path = EXAMPLES_DIR / "sample_employees.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Сотрудники"
    data = [
        ["ФИО", "Должность", "Отдел", "Оклад"],
        ["Иванов Иван Иванович", "Старший разработчик", "IT Департамент", "180 000 руб."],
        ["Петрова Анна Сергеевна", "Ведущий аналитик", "Финансовый отдел", "160 000 руб."],
        ["Сидоров Алексей Павлович", "Менеджер проектов", "Управление проектами", "150 000 руб."],
        ["Кузнецова Елена Дмитриевна", "HR-директор", "Управление персоналом", "190 000 руб."],
        ["Смирнов Михаил Васильевич", "Системный администратор", "Инфраструктура", "130 000 руб."],
    ]
    for row in data:
        ws.append(row)
    wb.save(str(xlsx_path))
    print(f"Created: {xlsx_path}")


if __name__ == "__main__":
    create_sample_docx()
    create_sample_csv()
    create_sample_xlsx()

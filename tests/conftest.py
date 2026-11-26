"""Pytest fixtures and test data generators for Flowdow tests."""

import csv
import io
from typing import Any

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document

from apps.accounts.models import User, UserRole
from apps.organizations.models import Organization, OrganizationSettings


def make_docx_bytes(paragraphs: list[str | list[str]]) -> bytes:
    """Creates in-memory DOCX bytes.

    If a paragraph is a list of strings, each string is added as an individual run,
    simulating Word's internal split runs.
    """
    doc = Document()
    for item in paragraphs:
        p = doc.add_paragraph()
        if isinstance(item, list):
            for run_text in item:
                p.add_run(run_text)
        else:
            p.add_run(item)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_uploaded_docx(
    filename: str = "template.docx",
    paragraphs: list[str | list[str]] | None = None,
) -> SimpleUploadedFile:
    """Returns a Django SimpleUploadedFile with synthetic DOCX contents."""
    if paragraphs is None:
        paragraphs = ["Hello {{ full_name }} from {{ group }}!"]
    content = make_docx_bytes(paragraphs)
    return SimpleUploadedFile(
        name=filename,
        content=content,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def make_csv_bytes(
    rows: list[list[Any]],
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> bytes:
    """Creates in-memory CSV bytes with the given delimiter and encoding (e.g. utf-8, utf-8-sig)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode(encoding)


def make_uploaded_csv(
    filename: str = "dataset.csv",
    rows: list[list[Any]] | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> SimpleUploadedFile:
    """Returns a Django SimpleUploadedFile with synthetic CSV contents."""
    if rows is None:
        rows = [
            ["ФИО", "Группа", "Специальность"],
            ["Иванов Иван", "ИС-21", "Разработка ПО"],
        ]
    content = make_csv_bytes(rows, delimiter=delimiter, encoding=encoding)
    return SimpleUploadedFile(
        name=filename,
        content=content,
        content_type="text/csv",
    )


def make_xlsx_bytes(
    sheets_data: dict[str, list[list[Any]]] | None = None,
) -> bytes:
    """Creates in-memory XLSX bytes with one or more worksheets."""
    wb = openpyxl.Workbook()
    if sheets_data is None:
        sheets_data = {"Sheet1": [["ФИО", "Оклад"], ["Иванов Иван", 100000]]}

    first = True
    for sheet_title, rows in sheets_data.items():
        if first:
            ws = wb.active
            ws.title = sheet_title
            first = False
        else:
            ws = wb.create_sheet(title=sheet_title)
        for row in rows:
            ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_uploaded_xlsx(
    filename: str = "dataset.xlsx",
    sheets_data: dict[str, list[list[Any]]] | None = None,
) -> SimpleUploadedFile:
    """Returns a Django SimpleUploadedFile with synthetic XLSX contents."""
    content = make_xlsx_bytes(sheets_data)
    return SimpleUploadedFile(
        name=filename,
        content=content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@pytest.fixture
def standard_user(db) -> User:
    """Creates a regular operator user."""
    return User.objects.create_user(
        username="testuser",
        email="testuser@flowdow.local",
        password="testpassword123",
        role=UserRole.OPERATOR,
        first_name="Alice",
        last_name="Operator",
    )


@pytest.fixture
def admin_user(db) -> User:
    """Creates an administrator user."""
    return User.objects.create_user(
        username="adminuser",
        email="admin@flowdow.local",
        password="adminpassword123",
        role=UserRole.ADMIN,
        is_staff=True,
        is_superuser=True,
        first_name="Bob",
        last_name="Admin",
    )


@pytest.fixture
def viewer_user(db) -> User:
    """Creates a read-only viewer user."""
    return User.objects.create_user(
        username="vieweruser",
        email="viewer@flowdow.local",
        password="viewerpassword123",
        role=UserRole.VIEWER,
        first_name="Victor",
        last_name="Viewer",
    )


@pytest.fixture
def manager_user(db) -> User:
    """Creates a manager user with org-wide operational access."""
    return User.objects.create_user(
        username="manageruser",
        email="manager@flowdow.local",
        password="managerpassword123",
        role=UserRole.MANAGER,
        first_name="Marina",
        last_name="Manager",
    )


@pytest.fixture
def other_operator_user(db) -> User:
    """Creates a second operator user for object-level BOLA tests."""
    return User.objects.create_user(
        username="operator2",
        email="operator2@flowdow.local",
        password="operator2password123",
        role=UserRole.OPERATOR,
        first_name="Oleg",
        last_name="Operator",
    )


@pytest.fixture
def default_organization(db) -> Organization:
    """Creates default organization."""
    org = Organization.objects.create(
        name="Flowdow Corp",
        legal_name="Flowdow Corporation LLC",
        tax_id="123456789",
    )
    OrganizationSettings.objects.create(organization=org)
    return org

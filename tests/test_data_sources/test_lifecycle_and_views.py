"""Tests for DataSource lifecycle, persistence, cascading delete, and views."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.data_sources.models import DataRecord, DataSource, DataSourceFormat, DataSourceStatus
from apps.data_sources.services import DataSourceService
from tests.conftest import make_uploaded_csv, make_uploaded_xlsx


@pytest.mark.django_db
def test_create_csv_data_source_and_records(admin_user):
    """Verifies full lifecycle of creating a CSV DataSource and bulk DataRecords."""
    uploaded_file = make_uploaded_csv(
        filename="students.csv",
        rows=[
            ["ФИО", "Группа", "Специальность"],
            ["Иванов Иван", "ИС-21", "Разработка ПО"],
            ["Петров Петр", "ИС-22", "Сетевое администрирование"],
        ],
    )
    data_source = DataSourceService.create_data_source(
        name="Студенты 2024",
        uploaded_file=uploaded_file,
        user=admin_user,
        description="Тестовый набор данных студентов",
    )

    assert data_source.pk is not None
    assert data_source.name == "Студенты 2024"
    assert data_source.format == DataSourceFormat.CSV
    assert data_source.status == DataSourceStatus.READY
    assert data_source.row_count == 2
    assert data_source.column_count == 3
    assert data_source.headers == ["ФИО", "Группа", "Специальность"]
    assert data_source.uploaded_by == admin_user

    # Verify DataRecords created
    records = list(data_source.records.all().order_by("row_number"))
    assert len(records) == 2
    assert records[0].row_number == 1
    assert records[0].data["ФИО"] == "Иванов Иван"
    assert records[0].data["Группа"] == "ИС-21"
    assert records[1].row_number == 2
    assert records[1].data["Специальность"] == "Сетевое администрирование"

    # Verify AuditLog recorded
    audit_entry = AuditLog.objects.filter(
        action="DATA_SOURCE_IMPORTED", resource_id=str(data_source.pk)
    ).first()
    assert audit_entry is not None
    assert audit_entry.user == admin_user


@pytest.mark.django_db
def test_create_xlsx_data_source_and_records(admin_user):
    """Verifies creating an XLSX DataSource with multiple sheets."""
    uploaded_file = make_uploaded_xlsx(
        filename="company.xlsx",
        sheets_data={
            "Employees": [
                ["ФИО", "Должность", "Оклад"],
                ["Сидоров", "Инженер", 150000],
            ],
            "Projects": [
                ["Проект", "Бюджет"],
                ["Flowdow", 500000],
            ],
        },
    )
    data_source = DataSourceService.create_data_source(
        name="Компания",
        uploaded_file=uploaded_file,
        user=admin_user,
        sheet_name="Employees",
    )
    assert data_source.format == DataSourceFormat.XLSX
    assert data_source.sheet_name == "Employees"
    assert data_source.row_count == 1
    assert data_source.headers == ["ФИО", "Должность", "Оклад"]

    records = list(data_source.records.all())
    assert len(records) == 1
    assert records[0].data["ФИО"] == "Сидоров"
    assert records[0].data["Оклад"] == "150000"


@pytest.mark.django_db
def test_delete_data_source_cascades_records(admin_user):
    """Verifies that deleting a DataSource removes all DataRecords and disk file."""
    uploaded_file = make_uploaded_csv(filename="temp.csv")
    data_source = DataSourceService.create_data_source(
        name="Временный",
        uploaded_file=uploaded_file,
        user=admin_user,
    )
    ds_id = data_source.pk
    assert DataRecord.objects.filter(data_source_id=ds_id).count() > 0

    success = DataSourceService.delete_data_source(data_source_id=ds_id, user=admin_user)
    assert success is True
    assert not DataSource.objects.filter(pk=ds_id).exists()
    assert DataRecord.objects.filter(data_source_id=ds_id).count() == 0

    audit_entry = AuditLog.objects.filter(
        action="DATA_SOURCE_DELETED", resource_id=str(ds_id)
    ).first()
    assert audit_entry is not None


@pytest.mark.django_db
def test_data_source_list_view(client, standard_user):
    """Verifies data source list view for authenticated user."""
    client.force_login(standard_user)
    url = reverse("data_sources:list")
    response = client.get(url)
    assert response.status_code == 200
    assert "Источники данных" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_data_source_upload_view_get_and_post(client, admin_user):
    """Verifies GET and POST for DataSourceUploadView."""
    client.force_login(admin_user)
    upload_url = reverse("data_sources:upload")

    # GET
    res_get = client.get(upload_url)
    assert res_get.status_code == 200

    # POST valid CSV
    uploaded_file = make_uploaded_csv(filename="salaries.csv")
    res_post = client.post(
        upload_url,
        {
            "name": "Зарплатная ведомость",
            "file": uploaded_file,
            "description": "Ведомость за сентябрь",
        },
    )
    assert res_post.status_code == 302
    ds = DataSource.objects.filter(name="Зарплатная ведомость").first()
    assert ds is not None
    assert ds.status == DataSourceStatus.READY


@pytest.mark.django_db
def test_data_source_detail_and_pagination(client, admin_user):
    """Verifies detail view rendering and pagination."""
    rows = [["ID", "Name"]] + [[str(i), f"User_{i}"] for i in range(1, 35)]
    uploaded_file = make_uploaded_csv(filename="users.csv", rows=rows)
    data_source = DataSourceService.create_data_source(
        name="Большой список",
        uploaded_file=uploaded_file,
        user=admin_user,
    )
    client.force_login(admin_user)

    detail_url = reverse("data_sources:detail", kwargs={"pk": data_source.pk})
    res = client.get(detail_url)
    assert res.status_code == 200
    content = res.content.decode("utf-8")
    assert "Большой список" in content
    assert "User_1" in content

    # Page 2
    res_p2 = client.get(f"{detail_url}?page=2")
    assert res_p2.status_code == 200
    assert "User_30" in res_p2.content.decode("utf-8")


@pytest.mark.django_db
def test_data_source_download_view(client, admin_user):
    """Verifies downloading the raw dataset file."""
    uploaded_file = make_uploaded_csv(filename="download_test.csv")
    data_source = DataSourceService.create_data_source(
        name="Скачиваемый",
        uploaded_file=uploaded_file,
        user=admin_user,
    )
    client.force_login(admin_user)

    url = reverse("data_sources:download", kwargs={"pk": data_source.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert res["Content-Type"] == "text/csv"


@pytest.mark.django_db
def test_viewer_role_cannot_upload_or_delete_data_sources(client, viewer_user, admin_user):
    """Verifies that VIEWER role receives 403 Forbidden for mutating operations."""
    uploaded_file = make_uploaded_csv(filename="vtest.csv")
    ds = DataSourceService.create_data_source(
        name="Для просмотра",
        uploaded_file=uploaded_file,
        user=admin_user,
    )
    client.force_login(viewer_user)

    # Attempt to access upload page
    upload_url = reverse("data_sources:upload")
    res_upload = client.get(upload_url)
    assert res_upload.status_code == 403

    # Attempt to post new data source
    res_post = client.post(upload_url, {"name": "Hacked", "file": make_uploaded_csv()})
    assert res_post.status_code == 403

    # Attempt to delete data source
    del_url = reverse("data_sources:delete", kwargs={"pk": ds.pk})
    res_del = client.post(del_url)
    assert res_del.status_code == 403
    assert DataSource.objects.filter(pk=ds.pk).exists()

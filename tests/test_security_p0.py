"""Comprehensive regression tests for P0 security controls across Flowdow."""

import io
import struct
import zipfile

import openpyxl
import pytest
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.template.loader import render_to_string
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.services import AuditService
from apps.core.archive_security import (
    DEFAULT_MAX_ZIP_ENTRIES,
    build_safe_file_response,
    validate_docx_archive,
    validate_xlsx_archive,
)
from apps.data_sources.models import DataSource, DataSourceFormat, DataSourceStatus
from apps.data_sources.services import (
    DataSourceSecurityValidator,
    DataSourceService,
    DataSourceValidationError,
    XlsxImportService,
)
from apps.documents.models import DocumentType
from apps.generation.services import DocumentGenerationService, GenerationValidationError
from apps.mapping.models import MappingConfig
from apps.mapping.services import MappingService
from apps.organizations.services import OrganizationService
from apps.templates_manager.services import (
    DocxSecurityValidator,
    TemplateService,
    TemplateValidationError,
)
from config import settings as project_settings
from tests.conftest import make_docx_bytes, make_uploaded_csv, make_uploaded_docx


def _build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    """Builds an uncompressed/deflated ZIP archive in memory from filename -> bytes mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _spoof_entry_uncompressed_size(zip_bytes: bytes, entry_name: str, fake_size: int) -> bytes:
    """Patches both local and central ZIP header uncompressed-size fields for a single entry."""
    data = bytearray(zip_bytes)
    name_bytes = entry_name.encode("utf-8")

    # Patch local file header (signature PK\x03\x04)
    local_sig = b"PK\x03\x04"
    pos = data.find(local_sig)
    while pos != -1:
        fname_len = struct.unpack_from("<H", data, pos + 26)[0]
        fname = bytes(data[pos + 30 : pos + 30 + fname_len])
        if fname == name_bytes:
            struct.pack_into("<I", data, pos + 22, fake_size)
        pos = data.find(local_sig, pos + 4)

    # Patch central directory header (signature PK\x01\x02)
    cd_sig = b"PK\x01\x02"
    pos = data.find(cd_sig)
    while pos != -1:
        fname_len = struct.unpack_from("<H", data, pos + 28)[0]
        fname = bytes(data[pos + 46 : pos + 46 + fname_len])
        if fname == name_bytes:
            struct.pack_into("<I", data, pos + 24, fake_size)
        pos = data.find(cd_sig, pos + 4)

    return bytes(data)


@pytest.fixture
def security_workspace_data(db, standard_user, other_operator_user):
    """Provisions objects owned by two different OPERATOR users and one unowned DataSource."""
    doc_type = DocumentType.objects.create(name="Договор оказания услуг")
    template = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx(
            filename="service_contract.docx",
            paragraphs=["Договор для {{ full_name }}"],
        ),
        name="Базовый шаблон договора",
        user=standard_user,
    )

    ds_owner1 = DataSourceService.create_data_source(
        name="Данные оператора 1",
        uploaded_file=make_uploaded_csv(
            filename="op1.csv",
            rows=[["ФИО"], ["Иванов Иван"]],
        ),
        user=standard_user,
    )
    ds_owner2 = DataSourceService.create_data_source(
        name="Данные оператора 2",
        uploaded_file=make_uploaded_csv(
            filename="op2.csv",
            rows=[["ФИО"], ["Петров Пётр"]],
        ),
        user=other_operator_user,
    )
    ds_unowned = DataSource.objects.create(
        name="Бесхозный набор",
        format=DataSourceFormat.CSV,
        status=DataSourceStatus.READY,
        headers=["ФИО"],
        row_count=0,
        uploaded_by=None,
    )

    mapping1 = MappingService.create_or_update_mapping_config(
        name="Схема оператора 1",
        template=template,
        data_source=ds_owner1,
        rules_data=[{"template_variable": "full_name", "source_column": "ФИО", "required": True}],
        user=standard_user,
    )
    mapping2 = MappingService.create_or_update_mapping_config(
        name="Схема оператора 2",
        template=template,
        data_source=ds_owner2,
        rules_data=[{"template_variable": "full_name", "source_column": "ФИО", "required": True}],
        user=other_operator_user,
    )

    batch1 = DocumentGenerationService.generate_batch(
        mapping_config=mapping1,
        data_records=list(ds_owner1.records.all()),
        user=standard_user,
    )
    batch2 = DocumentGenerationService.generate_batch(
        mapping_config=mapping2,
        data_records=list(ds_owner2.records.all()),
        user=other_operator_user,
    )

    AuditService.log(
        action="SENSITIVE_AUDIT_EVENT",
        resource_type="Organization",
        resource_id="1",
        user=standard_user,
    )

    return {
        "doc_type": doc_type,
        "template": template,
        "ds1": ds_owner1,
        "ds2": ds_owner2,
        "ds_unowned": ds_unowned,
        "mapping1": mapping1,
        "mapping2": mapping2,
        "batch1": batch1,
        "batch2": batch2,
    }


@pytest.mark.django_db
def test_viewer_blocked_from_settings_mutations_and_downloads(
    client, viewer_user, security_workspace_data
):
    """Verifies VIEWER gets 403 across settings, downloads, datasets, mappings, and generation."""
    data = security_workspace_data
    doc1 = data["batch1"].documents.first()
    assert doc1 is not None

    client.force_login(viewer_user)

    blocked_gets = [
        reverse("organizations:settings"),
        reverse("documents:create"),
        reverse("templates_manager:download", kwargs={"pk": data["template"].pk}),
        reverse("data_sources:list"),
        reverse("data_sources:upload"),
        reverse("data_sources:detail", kwargs={"pk": data["ds1"].pk}),
        reverse("data_sources:download", kwargs={"pk": data["ds1"].pk}),
        reverse("mapping:list"),
        reverse("mapping:create"),
        reverse("mapping:detail", kwargs={"pk": data["mapping1"].pk}),
        reverse("generation:list"),
        reverse("generation:wizard"),
        reverse("generation:detail", kwargs={"pk": data["batch1"].pk}),
        reverse("generation:download_zip", kwargs={"pk": data["batch1"].pk}),
        reverse("generation:download_doc", kwargs={"pk": doc1.pk}),
    ]
    for url in blocked_gets:
        assert client.get(url).status_code == 403, f"VIEWER must receive 403 on GET {url}"

    blocked_posts = [
        (reverse("organizations:settings"), {"name": "Hacked Org"}),
        (reverse("documents:create"), {"name": "Unauthorized Type"}),
        (
            reverse("documents:template_upload", kwargs={"pk": data["doc_type"].pk}),
            {"name": "Evil"},
        ),
        (reverse("templates_manager:activate", kwargs={"pk": data["template"].pk}), {}),
        (reverse("templates_manager:archive", kwargs={"pk": data["template"].pk}), {}),
        (reverse("data_sources:delete", kwargs={"pk": data["ds1"].pk}), {}),
        (reverse("mapping:delete", kwargs={"pk": data["mapping1"].pk}), {}),
        (
            reverse("generation:wizard"),
            {"mapping_id": data["mapping1"].pk, "select_all": "1"},
        ),
    ]
    for url, payload in blocked_posts:
        assert client.post(url, payload).status_code == 403, (
            f"VIEWER must receive 403 on POST {url}"
        )


@pytest.mark.django_db
def test_is_staff_on_viewer_does_not_bypass_rbac(client, security_workspace_data):
    """Ensures Django is_staff=True on a VIEWER account does not grant operational/admin rights."""
    viewer_staff = User.objects.create_user(
        username="viewer_staff",
        email="viewer_staff@flowdow.local",
        password="viewerpassword123",
        role=UserRole.VIEWER,
        is_staff=True,
        is_superuser=False,
    )
    data = security_workspace_data
    client.force_login(viewer_staff)

    for url in (
        reverse("organizations:settings"),
        reverse("data_sources:list"),
        reverse("mapping:list"),
        reverse("generation:list"),
        reverse("templates_manager:download", kwargs={"pk": data["template"].pk}),
    ):
        assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_viewer_dashboard_hides_audit_logs_and_batches(
    client, viewer_user, security_workspace_data
):
    """Ensures VIEWER dashboard renders metrics only and omits batches, audit logs, and admin links."""
    client.force_login(viewer_user)
    res = client.get(reverse("core:dashboard"))
    assert res.status_code == 200
    assert list(res.context["recent_batches"]) == []
    assert list(res.context["recent_activities"]) == []
    html = res.content.decode("utf-8")
    assert "SENSITIVE_AUDIT_EVENT" not in html
    assert reverse("organizations:settings") not in html
    assert reverse("data_sources:list") not in html


@pytest.mark.django_db
def test_service_layer_rbac_enforcement(viewer_user, manager_user, security_workspace_data):
    """Verifies direct service calls enforce permissions when user is passed."""
    data = security_workspace_data
    org = OrganizationService.get_or_create_default()

    with pytest.raises(PermissionDenied):
        OrganizationService.update_organization(
            org=org, name="Bypassed", legal_name="Bypassed", tax_id="1", user=manager_user
        )
    with pytest.raises(PermissionDenied):
        OrganizationService.update_organization(
            org=org, name="Bypassed", legal_name="Bypassed", tax_id="1", user=viewer_user
        )
    with pytest.raises(PermissionDenied):
        TemplateService.activate_template(data["template"], user=viewer_user)
    with pytest.raises(PermissionDenied):
        DataSourceService.delete_data_source(data["ds1"].pk, user=viewer_user)
    with pytest.raises(PermissionDenied):
        MappingService.delete_mapping_config(data["mapping1"].pk, user=viewer_user)
    with pytest.raises(PermissionDenied):
        DocumentGenerationService.generate_batch(
            mapping_config=data["mapping1"],
            data_records=list(data["ds1"].records.all()),
            user=viewer_user,
        )


@pytest.mark.django_db
def test_operator_bola_blocked_on_other_operator_and_unowned_objects(
    client, standard_user, other_operator_user, security_workspace_data
):
    """Verifies OPERATOR A cannot view, download, mutate, or use OPERATOR B's or unowned objects."""
    data = security_workspace_data
    doc2 = data["batch2"].documents.first()
    assert doc2 is not None

    client.force_login(standard_user)

    # DataSource IDOR / BOLA (other operator + unowned)
    for forbidden_ds in (data["ds2"], data["ds_unowned"]):
        assert (
            client.get(reverse("data_sources:detail", kwargs={"pk": forbidden_ds.pk})).status_code
            == 403
        )
        assert (
            client.get(reverse("data_sources:download", kwargs={"pk": forbidden_ds.pk})).status_code
            == 403
        )
        assert (
            client.post(reverse("data_sources:delete", kwargs={"pk": forbidden_ds.pk})).status_code
            == 403
        )
        assert DataSource.objects.filter(pk=forbidden_ds.pk).exists()
        assert (
            client.get(
                f"{reverse('mapping:create')}?template_id={data['template'].pk}&data_source_id={forbidden_ds.pk}"
            ).status_code
            == 403
        )
        assert (
            client.post(
                reverse("mapping:create"),
                {
                    "name": "Hijack",
                    "template": data["template"].pk,
                    "data_source": forbidden_ds.pk,
                    "col_full_name": "ФИО",
                    "req_full_name": "on",
                },
            ).status_code
            == 403
        )

    # Mapping IDOR / BOLA
    assert (
        client.get(reverse("mapping:detail", kwargs={"pk": data["mapping2"].pk})).status_code == 403
    )
    assert (
        client.post(reverse("mapping:delete", kwargs={"pk": data["mapping2"].pk})).status_code
        == 403
    )
    assert MappingConfig.objects.filter(pk=data["mapping2"].pk).exists()

    # Generation Wizard & Batch / Document Download BOLA
    assert (
        client.get(f"{reverse('generation:wizard')}?mapping_id={data['mapping2'].pk}").status_code
        == 403
    )
    assert (
        client.post(
            reverse("generation:wizard"),
            {"mapping_id": data["mapping2"].pk, "select_all": "1"},
        ).status_code
        == 403
    )
    assert (
        client.get(reverse("generation:detail", kwargs={"pk": data["batch2"].pk})).status_code
        == 403
    )
    assert (
        client.get(reverse("generation:download_zip", kwargs={"pk": data["batch2"].pk})).status_code
        == 403
    )
    assert client.get(reverse("generation:download_doc", kwargs={"pk": doc2.pk})).status_code == 403

    # List scoping checks
    ds_list_html = client.get(reverse("data_sources:list")).content.decode("utf-8")
    assert "Данные оператора 1" in ds_list_html
    assert "Данные оператора 2" not in ds_list_html
    assert "Бесхозный набор" not in ds_list_html

    mapping_list_html = client.get(reverse("mapping:list")).content.decode("utf-8")
    assert "Схема оператора 1" in mapping_list_html
    assert "Схема оператора 2" not in mapping_list_html

    gen_list_html = client.get(reverse("generation:list")).content.decode("utf-8")
    assert f"#{data['batch1'].id}" in gen_list_html
    assert f"#{data['batch2'].id}" not in gen_list_html

    # Service-layer cross-source record injection rejection
    with pytest.raises(GenerationValidationError):
        DocumentGenerationService.generate_batch(
            mapping_config=data["mapping1"],
            data_records=list(data["ds2"].records.all()),
            user=standard_user,
        )


@pytest.mark.django_db
def test_positive_flows_for_all_four_roles(
    client,
    admin_user,
    manager_user,
    standard_user,
    viewer_user,
    security_workspace_data,
):
    """Confirms expected positive capabilities for VIEWER, OPERATOR, MANAGER, and ADMIN."""
    data = security_workspace_data
    doc1 = data["batch1"].documents.first()
    doc2 = data["batch2"].documents.first()
    assert doc1 is not None and doc2 is not None

    # 1. VIEWER: read-only catalog & profile
    client.force_login(viewer_user)
    assert client.get(reverse("core:dashboard")).status_code == 200
    assert client.get(reverse("documents:list")).status_code == 200
    assert (
        client.get(reverse("documents:detail", kwargs={"pk": data["doc_type"].pk})).status_code
        == 200
    )
    assert client.get(reverse("templates_manager:list")).status_code == 200
    assert client.get(reverse("accounts:profile")).status_code == 200

    # 2. OPERATOR: full workflow on own resources + shared template download
    client.force_login(standard_user)
    assert (
        client.get(
            reverse("templates_manager:download", kwargs={"pk": data["template"].pk})
        ).status_code
        == 200
    )
    assert (
        client.get(reverse("data_sources:detail", kwargs={"pk": data["ds1"].pk})).status_code == 200
    )
    assert (
        client.get(reverse("data_sources:download", kwargs={"pk": data["ds1"].pk})).status_code
        == 200
    )
    assert (
        client.get(reverse("mapping:detail", kwargs={"pk": data["mapping1"].pk})).status_code == 200
    )
    assert (
        client.get(reverse("generation:detail", kwargs={"pk": data["batch1"].pk})).status_code
        == 200
    )
    assert (
        client.get(reverse("generation:download_zip", kwargs={"pk": data["batch1"].pk})).status_code
        == 200
    )
    assert client.get(reverse("generation:download_doc", kwargs={"pk": doc1.pk})).status_code == 200

    # 3. MANAGER: org-wide operational access & audit logs, denied org settings
    client.force_login(manager_user)
    dash_mgr = client.get(reverse("core:dashboard"))
    assert dash_mgr.status_code == 200
    assert len(dash_mgr.context["recent_activities"]) >= 1
    assert (
        client.get(reverse("data_sources:download", kwargs={"pk": data["ds2"].pk})).status_code
        == 200
    )
    assert (
        client.get(reverse("mapping:detail", kwargs={"pk": data["mapping2"].pk})).status_code == 200
    )
    assert client.get(reverse("generation:download_doc", kwargs={"pk": doc2.pk})).status_code == 200
    assert client.get(reverse("organizations:settings")).status_code == 403

    # 4. ADMIN: full access including organization settings
    client.force_login(admin_user)
    assert client.get(reverse("organizations:settings")).status_code == 200
    assert (
        client.post(
            reverse("organizations:settings"),
            {
                "name": "Updated Org",
                "legal_name": "Updated LLC",
                "tax_id": "7700112233",
                "default_date_format": "d.m.Y",
                "default_currency": "RUB",
                "retention_days": "365",
            },
        ).status_code
        == 302
    )
    assert client.get(reverse("generation:download_doc", kwargs={"pk": doc2.pk})).status_code == 200


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_media_direct_url_not_served_even_in_debug(client, admin_user, security_workspace_data):
    """SEC-004: Verifies raw /media/... paths return 404 even when DEBUG=True."""
    data = security_workspace_data
    template_rel = data["template"].file.name
    ds_rel = data["ds1"].file.name
    zip_rel = data["batch1"].output_file.name

    for rel_path in (template_rel, ds_rel, zip_rel):
        media_url = f"/media/{rel_path}"
        # Anonymous user
        assert client.get(media_url).status_code == 404
        # Authenticated user
        client.force_login(admin_user)
        assert client.get(media_url).status_code == 404
        client.logout()

    # Authorized view download includes nosniff and attachment headers
    client.force_login(admin_user)
    dl = client.get(reverse("templates_manager:download", kwargs={"pk": data["template"].pk}))
    assert dl.status_code == 200
    assert dl["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in dl["Content-Disposition"]


def test_build_safe_file_response_rejects_path_outside_media_root(tmp_path):
    """Verifies build_safe_file_response refuses paths outside settings.MEDIA_ROOT."""
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("sensitive", encoding="utf-8")

    class _FakeField:
        path = str(outside_file)

        def __bool__(self):
            return True

    with pytest.raises(Http404):
        build_safe_file_response(_FakeField(), "secret.txt")


@pytest.mark.django_db
def test_open_redirect_blocked_on_template_actions_and_login(
    client, admin_user, standard_user, security_workspace_data
):
    """Verifies external next/Referer targets are ignored on template actions and login."""
    tpl = security_workspace_data["template"]
    client.force_login(admin_user)

    for url in (
        reverse("templates_manager:archive", kwargs={"pk": tpl.pk}),
        reverse("templates_manager:activate", kwargs={"pk": tpl.pk}),
    ):
        for evil in (
            "https://evil.example/phish",
            "//evil.example/phish",
            "http://169.254.169.254/",
        ):
            res = client.post(f"{url}?next={evil}", HTTP_REFERER=evil)
            assert res.status_code == 302
            assert res["Location"] == reverse(
                "documents:detail", kwargs={"pk": tpl.document_type.pk}
            )

    # Confirm valid local next still works safely
    safe_next = reverse("templates_manager:list")
    res_safe = client.post(
        f"{reverse('templates_manager:activate', kwargs={'pk': tpl.pk})}?next={safe_next}"
    )
    assert res_safe.status_code == 302
    assert res_safe["Location"] == safe_next

    # Confirm Django LoginView blocks external next redirects
    client.logout()
    login_res = client.post(
        f"{reverse('accounts:login')}?next=https://evil.example/steal",
        {"username": standard_user.username, "password": "testpassword123"},
    )
    assert login_res.status_code == 302
    assert not login_res["Location"].startswith("https://evil.example")


@pytest.mark.django_db
def test_logout_requires_post_and_enforces_csrf(standard_user):
    """Verifies GET /accounts/logout/ returns 405 and POST requires valid CSRF token."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(standard_user)

    # GET logout must be rejected without terminating session
    res_get = csrf_client.get(reverse("accounts:logout"))
    assert res_get.status_code == 405
    assert csrf_client.get(reverse("core:dashboard")).status_code == 200

    # POST logout without CSRF token must fail with 403
    res_post_no_csrf = csrf_client.post(reverse("accounts:logout"))
    assert res_post_no_csrf.status_code == 403
    assert csrf_client.get(reverse("core:dashboard")).status_code == 200

    # POST logout with CSRF token succeeds
    dashboard_html = csrf_client.get(reverse("core:dashboard")).content.decode("utf-8")
    assert 'name="csrfmiddlewaretoken"' in dashboard_html
    csrf_token = csrf_client.cookies["csrftoken"].value
    res_post_ok = csrf_client.post(
        reverse("accounts:logout"),
        {"csrfmiddlewaretoken": csrf_token},
    )
    assert res_post_ok.status_code == 302
    assert csrf_client.get(reverse("core:dashboard")).status_code == 302


def test_zip_bomb_and_spoofed_metadata_rejected_for_docx_and_xlsx(monkeypatch):
    """SEC-005: Rejects spoofed headers and high-ratio ZIP bombs before docxtpl/openpyxl."""
    called = {"openpyxl": False}

    def _fail_openpyxl(*args, **kwargs):
        called["openpyxl"] = True
        raise AssertionError("openpyxl must not be invoked for invalid XLSX archives")

    monkeypatch.setattr(openpyxl, "load_workbook", _fail_openpyxl)

    # High-ratio valid XML payload (>100x compression ratio): ~2.5 MiB spaces -> ~3 KiB compressed
    huge_spaces = b" " * (2500 * 1024)
    docx_bomb = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "word/document.xml": (
                b'<?xml version="1.0"?><document><!-- ' + huge_spaces + b" --></document>"
            ),
        }
    )
    spoofed_docx = _spoof_entry_uncompressed_size(docx_bomb, "word/document.xml", fake_size=64)
    assert len(spoofed_docx) < 20_000

    with zipfile.ZipFile(io.BytesIO(spoofed_docx), "r") as zf:
        # Header falsely reports only 64 bytes for word/document.xml
        assert zf.getinfo("word/document.xml").file_size == 64

    # Spoofed DOCX rejected before docxtpl runs
    with pytest.raises(TemplateValidationError):
        DocxSecurityValidator.validate_file(
            SimpleUploadedFile("bomb.docx", spoofed_docx), filename="bomb.docx"
        )

    # Spoofed XLSX rejected before openpyxl.load_workbook runs
    xlsx_bomb = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "xl/workbook.xml": (
                b'<?xml version="1.0"?><workbook><!-- ' + huge_spaces + b" --></workbook>"
            ),
        }
    )
    spoofed_xlsx = _spoof_entry_uncompressed_size(xlsx_bomb, "xl/workbook.xml", fake_size=64)

    with pytest.raises(DataSourceValidationError):
        DataSourceSecurityValidator.validate_file(SimpleUploadedFile("bomb.xlsx", spoofed_xlsx))
    with pytest.raises(DataSourceValidationError):
        XlsxImportService.get_sheet_names(io.BytesIO(spoofed_xlsx))
    with pytest.raises(DataSourceValidationError):
        XlsxImportService.parse_file(io.BytesIO(spoofed_xlsx))

    assert called["openpyxl"] is False


def test_zip_entry_count_path_traversal_and_encrypted_archive_rejected():
    """SEC-005/SEC-009: Rejects excessive entry count, path traversal, and encrypted entries."""
    # Entry count bomb
    too_many_entries = {f"word/p{i}.xml": b"<x/>" for i in range(DEFAULT_MAX_ZIP_ENTRIES + 1)}
    too_many_entries["[Content_Types].xml"] = b'<?xml version="1.0"?><Types/>'
    too_many_entries["word/document.xml"] = b'<?xml version="1.0"?><document/>'
    excess_zip = _build_zip_bytes(too_many_entries)
    with pytest.raises(TemplateValidationError):
        validate_docx_archive(
            io.BytesIO(excess_zip),
            max_file_size=10 * 1024 * 1024,
            error_cls=TemplateValidationError,
        )

    # Path traversal entry inside archive
    traversal_zip = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "word/document.xml": b'<?xml version="1.0"?><document/>',
            "../outside.xml": b"<evil/>",
        }
    )
    with pytest.raises(TemplateValidationError):
        validate_docx_archive(
            io.BytesIO(traversal_zip),
            max_file_size=10 * 1024 * 1024,
            error_cls=TemplateValidationError,
        )

    # Encrypted flag bit set in central directory (flag_bits bit 0)
    raw = bytearray(
        _build_zip_bytes(
            {
                "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
                "xl/workbook.xml": b'<?xml version="1.0"?><workbook/>',
            }
        )
    )
    cd_pos = raw.find(b"PK\x01\x02")
    assert cd_pos != -1
    current_flags = struct.unpack_from("<H", raw, cd_pos + 8)[0]
    struct.pack_into("<H", raw, cd_pos + 8, current_flags | 0x0001)
    with pytest.raises(DataSourceValidationError):
        validate_xlsx_archive(
            io.BytesIO(bytes(raw)),
            max_file_size=20 * 1024 * 1024,
            error_cls=DataSourceValidationError,
        )


def test_xxe_doctype_entity_and_xml_depth_bomb_rejected_for_docx_and_xlsx():
    """SEC-009: Rejects DOCTYPE/ENTITY declarations and deep XML bombs in DOCX and XLSX."""
    xxe_payload = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b"<document>&xxe;</document>"
    )
    xxe_docx = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "word/document.xml": xxe_payload,
        }
    )
    with pytest.raises(TemplateValidationError):
        DocxSecurityValidator.validate_file(SimpleUploadedFile("xxe.docx", xxe_docx), "xxe.docx")

    xxe_xlsx = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "xl/workbook.xml": xxe_payload,
        }
    )
    with pytest.raises(DataSourceValidationError):
        DataSourceSecurityValidator.validate_file(SimpleUploadedFile("xxe.xlsx", xxe_xlsx))

    # Deep XML nesting (> 100 elements deep)
    open_tags = b"".join(f"<a{i}>".encode() for i in range(130))
    close_tags = b"".join(f"</a{i}>".encode() for i in reversed(range(130)))
    deep_xml = b'<?xml version="1.0" encoding="UTF-8"?>' + open_tags + close_tags
    deep_xlsx = _build_zip_bytes(
        {
            "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
            "xl/workbook.xml": deep_xml,
        }
    )
    with pytest.raises(DataSourceValidationError):
        validate_xlsx_archive(
            io.BytesIO(deep_xlsx),
            max_file_size=20 * 1024 * 1024,
            error_cls=DataSourceValidationError,
        )

    # Ensure valid baseline DOCX passes all security checks
    valid_docx = make_docx_bytes(["Valid {{ full_name }}"])
    DocxSecurityValidator.validate_file(SimpleUploadedFile("ok.docx", valid_docx), "ok.docx")


def test_production_settings_validation_rejects_weak_defaults():
    """Verifies production settings guardrails reject weak SECRET_KEY, wildcard hosts, and default DB password."""
    strong_secret = "xK9!qR2#vT7$zP4%mL8^nW3&yB6*cD5(jF1)hG0+sA9=wE2!uY7@"

    # Empty or known fallback SECRET_KEY rejected when debug=False
    with pytest.raises(ImproperlyConfigured):
        project_settings.validate_production_settings(
            debug=False,
            secret_key="flowdow-dev-secret-key-insecure-replace-in-production-min-50-chars-here",
            allowed_hosts=["flowdow.internal"],
            db_engine="django.db.backends.postgresql",
            db_password="StrongUniquePassword123!",
        )

    # Short SECRET_KEY rejected
    with pytest.raises(ImproperlyConfigured):
        project_settings.validate_production_settings(
            debug=False,
            secret_key="short-secret",
            allowed_hosts=["flowdow.internal"],
            db_engine="django.db.backends.postgresql",
            db_password="StrongUniquePassword123!",
        )

    # Missing, wildcard, or 0.0.0.0 ALLOWED_HOSTS rejected
    for bad_hosts in ([], ["*"], ["0.0.0.0"]):
        with pytest.raises(ImproperlyConfigured):
            project_settings.validate_production_settings(
                debug=False,
                secret_key=strong_secret,
                allowed_hosts=bad_hosts,
                db_engine="django.db.backends.postgresql",
                db_password="StrongUniquePassword123!",
            )

    # Default DB_PASSWORD rejected on PostgreSQL
    with pytest.raises(ImproperlyConfigured):
        project_settings.validate_production_settings(
            debug=False,
            secret_key=strong_secret,
            allowed_hosts=["flowdow.internal"],
            db_engine="django.db.backends.postgresql",
            db_password="flowdow_secure_password",
        )

    # Strong config accepted cleanly
    project_settings.validate_production_settings(
        debug=False,
        secret_key=strong_secret,
        allowed_hosts=["flowdow.internal"],
        db_engine="django.db.backends.postgresql",
        db_password="StrongUniquePassword123!",
    )

    # Baseline secure headers & no hardcoded dev secret or 0.0.0.0 default in settings code
    assert (
        project_settings.SECRET_KEY
        != "flowdow-dev-secret-key-insecure-replace-in-production-min-50-chars-here"
    )
    assert "0.0.0.0" not in project_settings._default_allowed_hosts
    assert project_settings.SESSION_COOKIE_HTTPONLY is True
    assert project_settings.CSRF_COOKIE_HTTPONLY is True
    assert project_settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert project_settings.X_FRAME_OPTIONS == "DENY"


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
def test_debug_false_hides_tracebacks_and_health_internals(client, viewer_user, monkeypatch):
    """Verifies DEBUG=False returns clean error pages and redacted health errors."""

    # HealthCheck endpoint hides DB exception message and vendor
    def _broken_cursor(*args, **kwargs):
        raise RuntimeError("FATAL password authentication failed for internal-db:5432")

    from django.db import connections

    with monkeypatch.context() as mp:
        mp.setattr(connections["default"], "cursor", _broken_cursor)
        health_res = client.get(reverse("core:health"))
    assert health_res.status_code == 503
    payload = health_res.json()
    assert payload == {"status": "unhealthy", "database": {"healthy": False}}
    assert "internal-db" not in health_res.content.decode("utf-8")

    # 404 page in DEBUG=False reveals no URLconf patterns or file paths
    not_found_res = client.get("/nonexistent-security-probe-url/")
    assert not_found_res.status_code == 404
    not_found_html = not_found_res.content.decode("utf-8")
    assert "Traceback" not in not_found_html
    assert "URLconf" not in not_found_html

    # 403 page renders cleanly without traceback
    client.force_login(viewer_user)
    forbidden_res = client.get(reverse("organizations:settings"))
    assert forbidden_res.status_code == 403
    forbidden_html = forbidden_res.content.decode("utf-8")
    assert "403" in forbidden_html
    assert "Traceback" not in forbidden_html

    # 500 error template renders standalone without context errors or internal details
    rendered_500 = render_to_string("500.html", {})
    assert "500" in rendered_500
    assert "Traceback" not in rendered_500

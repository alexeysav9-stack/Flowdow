"""Security regression and positive functionality tests for DOCX template RCE protection (SEC-001)."""

import io
import zipfile
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document
from jinja2 import nodes

from apps.core.template_security import (
    TemplateSecurityError,
    create_safe_jinja_environment,
)
from apps.data_sources.services import DataSourceService
from apps.documents.models import DocumentType
from apps.generation.models import BatchStatus, GenerationDocumentStatus
from apps.generation.services import DocumentGenerationService, GenerationError
from apps.mapping.services import MappingService
from apps.templates_manager.models import Template
from apps.templates_manager.services import (
    TemplateInspectionService,
    TemplateService,
    TemplateValidationError,
)
from tests.conftest import make_docx_bytes, make_uploaded_csv, make_uploaded_docx

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _make_docx_with_header_footer(
    body_text: str = "Valid {{ full_name }}",
    header_text: str = "",
    footer_text: str = "",
) -> bytes:
    """Builds a synthetic DOCX containing custom header/footer text."""
    doc = Document()
    doc.add_paragraph(body_text)
    if header_text:
        doc.sections[0].header.paragraphs[0].text = header_text
    if footer_text:
        doc.sections[0].footer.paragraphs[0].text = footer_text
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_docx_with_core_property(prop_name: str, prop_value: str) -> bytes:
    """Builds a synthetic DOCX with a payload placed inside core properties."""
    doc = Document()
    doc.add_paragraph("Normal body {{ full_name }}")
    setattr(doc.core_properties, prop_name, prop_value)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_docx_with_footnote(footnote_text: str) -> bytes:
    """Builds a synthetic DOCX containing a word/footnotes.xml part."""
    base_bytes = make_docx_bytes(["Normal body {{ full_name }}"])
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_bytes), "r") as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    b"</Types>",
                    (
                        b'<Override PartName="/word/footnotes.xml" '
                        b'ContentType="application/vnd.openxmlformats-officedocument'
                        b'.wordprocessingml.footnotes+xml"/></Types>'
                    ),
                )
            elif item.filename == "word/_rels/document.xml.rels":
                data = data.replace(
                    b"</Relationships>",
                    (
                        b'<Relationship Id="rId99" '
                        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" '
                        b'Target="footnotes.xml"/></Relationships>'
                    ),
                )
            zout.writestr(item, data)

        footnotes_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:footnote w:id="1"><w:p><w:r><w:t>{footnote_text}</w:t></w:r></w:p></w:footnote>'
            "</w:footnotes>"
        )
        zout.writestr("word/footnotes.xml", footnotes_xml.encode("utf-8"))
    return out.getvalue()


def _make_docx_with_table_cell(cell_text: str) -> bytes:
    """Builds a synthetic DOCX with a table cell containing the provided template text."""
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Label"
    table.rows[0].cells[1].text = cell_text
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _assert_rejected_everywhere(
    tmp_path: Path, docx_bytes: bytes, context: dict | None = None
) -> None:
    """Asserts that a dangerous DOCX is rejected by BOTH inspection and rendering."""
    buf = io.BytesIO(docx_bytes)
    with pytest.raises(TemplateValidationError) as inspect_exc:
        TemplateInspectionService.inspect_file(buf, filename="attack.docx")

    inspect_msg = str(inspect_exc.value)
    assert "Traceback" not in inspect_msg
    assert str(tmp_path) not in inspect_msg

    attack_path = tmp_path / "attack.docx"
    attack_path.write_bytes(docx_bytes)
    with pytest.raises(GenerationError) as render_exc:
        DocumentGenerationService.render_template_to_stream(str(attack_path), context or {})

    render_msg = str(render_exc.value)
    assert "Traceback" not in render_msg
    assert str(attack_path) not in render_msg
    assert str(tmp_path) not in render_msg


@pytest.mark.parametrize(
    "payload",
    [
        # 1. cycler.__init__.__globals__ chains (without running host commands)
        "{{ cycler.__init__.__globals__ }}",
        "{{ cycler.__init__.__globals__['os'] }}",
        "{{ cycler.__init__.__globals__.canary }}",
        # 2. __class__, __mro__, __subclasses__ traversal
        "{{ ''.__class__ }}",
        "{{ ''.__class__.__mro__ }}",
        "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        "{{ ().__class__.__base__.__subclasses__() }}",
        "{{ full_name.__class__ }}",
        "{{ full_name.__class__.__mro__ }}",
        "{{ full_name._private_attr }}",
        "{{ __class__ }}",
        "{{ _secret }}",
        # 3. Arbitrary function / callable invocations
        "{{ canary() }}",
        "{{ range(5) }}",
        "{{ dict(a=1) }}",
        "{{ lipsum() }}",
        "{{ open('dummy') }}",
        "{{ eval('1+1') }}",
        "{{ (full_name | upper)() }}",
        # 4. Attempts to access system modules / builtins / internal objects
        "{{ os }}",
        "{{ sys }}",
        "{{ subprocess }}",
        "{{ importlib }}",
        "{{ builtins }}",
        "{{ __builtins__ }}",
        "{{ __import__ }}",
        "{{ joiner.__init__.__globals__ }}",
        "{{ namespace.__init__.__globals__ }}",
        "{{ self }}",
        # 5. Dangerous Jinja2 filters and globals
        "{{ cycler }}",
        "{{ joiner }}",
        "{{ lipsum }}",
        "{{ namespace }}",
        "{{ range }}",
        "{{ dict }}",
        "{{ full_name | attr('__class__') }}",
        "{{ full_name | attr('__init__') | attr('__globals__') }}",
        "{{ full_name | map('upper') }}",
        "{{ full_name | select('defined') }}",
        "{{ full_name | reject('defined') }}",
        "{{ full_name | selectattr('__class__') }}",
        "{{ full_name | rejectattr('__class__') }}",
        "{{ full_name | groupby('__class__') }}",
        "{{ full_name | sort(attribute='__class__') }}",
        "{{ full_name | unique(attribute='__class__') }}",
        "{{ full_name | min(attribute='__class__') }}",
        "{{ full_name | max(attribute='__class__') }}",
        "{{ full_name | sum(attribute='__class__') }}",
        "{{ full_name | join(attribute='__class__') }}",
        "{{ '%s' | format(full_name) }}",
        "{{ full_name | pprint }}",
        "{{ full_name | xmlattr }}",
        "{{ full_name | tojson }}",
        "{{ full_name | urlize }}",
        "{{ full_name | urlencode }}",
        # 6. Alternative syntax / AST bypass attempts
        "{% set x = cycler %}{{ x }}",
        "{% set a = '_' ~ '_' ~ 'class' ~ '_' ~ '_' %}{{ full_name | attr(a) }}",
        "{% with x = full_name %}{{ x }}{% endwith %}",
        "{% macro m(x) %}{{ x }}{% endmacro %}{{ m(full_name) }}",
        "{% call full_name() %}{% endcall %}",
        "{% filter upper %}{{ full_name }}{% endfilter %}",
        "{% print cycler.__init__.__globals__ %}",
        "{% print full_name %}",
        "{% for ch in full_name %}{{ ch }}{% endfor %}",
        "{% if full_name %}{{ full_name }}{% endif %}",
        "{{ full_name if full_name else 'x' }}",
        "{% import 'os' as os %}",
        "{% from 'os' import path %}",
        "{% include 'other.xml' %}",
        "{% extends 'base.xml' %}",
        "{% autoescape false %}{{ full_name }}{% endautoescape %}",
        "{% raw %}{{ cycler }}{% endraw %}",
        "{{ '%s' % full_name }}",
        "{{ full_name ~ full_name }}",
        "{{ 2 ** 1000 }}",
        "{{ full_name * 100 }}",
        "{{ ['__class__'] }}",
        "{{ {'a': full_name} }}",
        "{{ (full_name, 'x') }}",
        "{{ full_name[0] }}",
        "{{ full_name['__class__'] }}",
        "{{ full_name.upper }}",
        "{{ full_name | upper.lower }}",
        "{{ full_name | upper('extra') }}",
        "{{ full_name | default(unknown_kw='x') }}",
        "{{ 𝐜𝐲𝐜𝐥𝐞𝐫 }}",
    ],
)
def test_dangerous_and_bypass_payloads_rejected(tmp_path: Path, payload: str):
    """Verifies all dangerous expressions and AST bypass variants are rejected at both layers."""
    canary_called = False

    def canary(*_args, **_kwargs):
        nonlocal canary_called
        canary_called = True
        return "CANARY_EXECUTED"

    docx_bytes = make_docx_bytes([payload])
    _assert_rejected_everywhere(
        tmp_path,
        docx_bytes,
        context={"full_name": "Иван", "canary": canary},
    )
    assert canary_called is False


def test_split_xml_runs_and_smart_quotes_bypass_rejected(tmp_path: Path):
    """Verifies split XML runs and Word smart-quote normalization cannot bypass validation."""
    split_payload = make_docx_bytes(
        [
            ["{{", " cycler.", "__init__", ".__globals__", " }}"],
        ]
    )
    _assert_rejected_everywhere(tmp_path, split_payload)

    smart_quote_payload = make_docx_bytes(
        [
            "{{ full_name | attr(‘__class__’) }}",
        ]
    )
    _assert_rejected_everywhere(tmp_path, smart_quote_payload, context={"full_name": "test"})


def test_docxtpl_table_tags_and_dyn_args_rejected(tmp_path: Path):
    """Verifies docxtpl colspan/cellbg rewriting and dynamic filter args cannot bypass AST rules."""
    colspan_attack = _make_docx_with_table_cell("{% colspan cycler.__init__ %}")
    _assert_rejected_everywhere(tmp_path, colspan_attack)

    cellbg_attack = _make_docx_with_table_cell("{% cellbg ''.__class__ %}")
    _assert_rejected_everywhere(tmp_path, cellbg_attack)

    dyn_args_attack = make_docx_bytes(["{{ full_name | default(*extra_args) }}"])
    _assert_rejected_everywhere(
        tmp_path,
        dyn_args_attack,
        context={"full_name": "test", "extra_args": ["fallback"]},
    )


def test_hidden_docx_parts_rejected(tmp_path: Path):
    """Verifies headers, footers, footnotes, and core properties are all validated equally."""
    header_attack = _make_docx_with_header_footer(header_text="{{ cycler.__init__.__globals__ }}")
    _assert_rejected_everywhere(tmp_path, header_attack, context={"full_name": "Alice"})

    footer_attack = _make_docx_with_header_footer(footer_text="{{ ''.__class__.__mro__ }}")
    _assert_rejected_everywhere(tmp_path, footer_attack, context={"full_name": "Alice"})

    footnote_attack = _make_docx_with_footnote("{{ lipsum.__globals__ }}")
    _assert_rejected_everywhere(tmp_path, footnote_attack, context={"full_name": "Alice"})

    for prop in ("title", "author", "comments", "subject", "identifier", "language"):
        prop_attack = _make_docx_with_core_property(prop, "{{ cycler.__init__.__globals__ }}")
        _assert_rejected_everywhere(tmp_path, prop_attack, context={"full_name": "Alice"})


def test_sandboxed_environment_defense_in_depth():
    """Verifies SandboxedEnvironment runtime hardening even independent of AST parser."""
    env = create_safe_jinja_environment()
    assert env.globals == {}
    assert env.tests == {}
    assert set(env.filters.keys()) == {
        "upper",
        "lower",
        "capitalize",
        "title",
        "trim",
        "replace",
        "default",
        "d",
    }

    assert env.is_safe_attribute("abc", "upper", str.upper) is False
    assert env.is_safe_callable(lambda: None) is False

    with pytest.raises(TemplateSecurityError):
        env.getattr("abc", "__class__")
    with pytest.raises(TemplateSecurityError):
        env.getitem({"a": 1}, "a")
    with pytest.raises(TemplateSecurityError):
        env.overlay(autoescape=True)
    with pytest.raises(TemplateSecurityError):
        env.add_extension("jinja2.ext.do")

    # Direct AST compilation bypass attempt must also be blocked in compile()
    forged_ast = nodes.Template(
        [nodes.Output([nodes.Call(nodes.Name("eval", "load"), [], [], None, None)])]
    )
    with pytest.raises(TemplateSecurityError):
        env.compile(forged_ast)


@pytest.mark.django_db
def test_upload_view_and_batch_error_handling_do_not_leak_internals(
    client,
    admin_user,
    settings,
    tmp_path: Path,
):
    """Verifies HTTP upload and batch generation errors never leak tracebacks or server paths."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
    doc_type = DocumentType.objects.create(name="Проверка безопасности")
    client.force_login(admin_user)

    upload_url = reverse("documents:template_upload", kwargs={"pk": doc_type.pk})
    malicious_file = make_uploaded_docx(
        filename="evil.docx",
        paragraphs=["{{ cycler.__init__.__globals__ }}"],
    )
    response = client.post(
        upload_url,
        {"name": "Evil", "file": malicious_file, "status": "active"},
        follow=True,
    )
    assert response.status_code == 200
    assert Template.objects.filter(document_type=doc_type).count() == 0
    content = response.content.decode("utf-8")
    assert "Traceback" not in content
    assert "/home/" not in content
    assert "cycler.__init__" not in content

    # Simulate a tampered/legacy template already stored on disk reaching generation
    safe_tpl = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=make_uploaded_docx("safe.docx", ["{{ full_name }}"]),
        name="Tampered",
        user=admin_user,
    )
    Path(safe_tpl.file.path).write_bytes(make_docx_bytes(["{{ ''.__class__.__mro__ }}"]))

    data_source = DataSourceService.create_data_source(
        name="Тест данные",
        uploaded_file=make_uploaded_csv("data.csv", [["ФИО"], ["Иван Иванов"]]),
        user=admin_user,
    )
    mapping = MappingService.create_or_update_mapping_config(
        name="Маппинг",
        template=safe_tpl,
        data_source=data_source,
        rules_data=[{"template_variable": "full_name", "source_column": "ФИО", "required": True}],
        user=admin_user,
    )
    records = list(data_source.records.all())
    wizard_res = client.post(
        reverse("generation:wizard"),
        {"mapping_id": mapping.id, "record_ids": [str(r.id) for r in records]},
        follow=True,
    )
    assert wizard_res.status_code == 200
    wizard_html = wizard_res.content.decode("utf-8")
    assert "Traceback" not in wizard_html
    assert str(tmp_path) not in wizard_html

    batch = DocumentGenerationService.generate_batch(
        mapping_config=mapping,
        data_records=records,
        user=admin_user,
    )
    assert batch.status == BatchStatus.FAILED
    assert batch.failed_records == 1
    failed_doc = batch.documents.first()
    assert failed_doc is not None
    assert failed_doc.status == GenerationDocumentStatus.FAILED
    assert "Traceback" not in failed_doc.error_message
    assert safe_tpl.file.path not in failed_doc.error_message


def test_positive_regular_and_missing_variables_and_allowed_filters(tmp_path: Path):
    """Verifies normal variables, missing variables, and safe allowlisted filters render properly."""
    docx_bytes = _make_docx_with_header_footer(
        body_text=(
            "ФИО: {{ фио | trim | upper }}; "
            "Нижний: {{ role | lower }}; "
            "Заголовок: {{ city | title }}; "
            "Заглавная: {{ note | capitalize }}; "
            "Замена: {{ code | replace('-', '_', count=1) }}; "
            "Отсутствует: [{{ missing_var }}]; "
            "По умолчанию: {{ missing_var | default('Нет данных') }}; "
            "Короткий default: {{ empty_var | d('Пусто', true) }}."
        ),
        header_text="Документ {{ doc_num }}",
        footer_text="Платформа {{ system_platform }}",
    )
    variables = TemplateInspectionService.inspect_file(
        io.BytesIO(docx_bytes), filename="valid.docx"
    )
    assert variables == [
        "city",
        "code",
        "doc_num",
        "empty_var",
        "missing_var",
        "note",
        "role",
        "system_platform",
        "фио",
    ]

    tpl_path = tmp_path / "valid.docx"
    tpl_path.write_bytes(docx_bytes)
    rendered_stream = DocumentGenerationService.render_template_to_stream(
        str(tpl_path),
        {
            "фио": "  Иванов Иван  ",
            "role": "ENGINEER",
            "city": "saint petersburg",
            "note": "approved note",
            "code": "A-10-B",
            "empty_var": "",
            "doc_num": "42",
            "system_platform": "Flowdow",
        },
    )
    out_doc = Document(rendered_stream)
    body = out_doc.paragraphs[0].text
    assert "ФИО: ИВАНОВ ИВАН" in body
    assert "Нижний: engineer" in body
    assert "Заголовок: Saint Petersburg" in body
    assert "Заглавная: Approved note" in body
    assert "Замена: A_10-B" in body
    assert "Отсутствует: []" in body
    assert "По умолчанию: Нет данных" in body
    assert "Короткий default: Пусто" in body
    assert "Документ 42" in out_doc.sections[0].header.paragraphs[0].text
    assert "Платформа Flowdow" in out_doc.sections[0].footer.paragraphs[0].text


@pytest.mark.parametrize(
    "sample_filename",
    [
        "sample_certificate.docx",
        "sample_certificate_ru.docx",
        "sample_certificate_en.docx",
        "sample_certificate_eng.docx",
    ],
)
def test_positive_existing_example_templates(sample_filename: str):
    """Verifies existing repository example DOCX templates pass inspection and render cleanly."""
    sample_path = EXAMPLES_DIR / sample_filename
    assert sample_path.exists()

    with sample_path.open("rb") as fh:
        variables = TemplateInspectionService.inspect_file(fh, filename=sample_filename)

    assert variables == ["current_date", "department", "full_name", "position", "salary"]

    out_stream = DocumentGenerationService.render_template_to_stream(
        str(sample_path),
        {
            "full_name": "Иванов Иван Иванович",
            "position": "Старший разработчик",
            "department": "IT Департамент",
            "salary": "180 000 руб.",
            "current_date": "24.11.2026",
        },
    )
    rendered_doc = Document(out_stream)
    all_text = " ".join(
        [p.text for p in rendered_doc.paragraphs]
        + [c.text for t in rendered_doc.tables for r in t.rows for c in r.cells]
    )
    assert "Иванов Иван Иванович" in all_text
    assert "Старший разработчик" in all_text
    assert "24.11.2026" in all_text
    assert "{{" not in all_text


@pytest.mark.django_db
def test_positive_batch_generation_with_filters_and_missing_optional_var(
    admin_user,
    settings,
    tmp_path: Path,
):
    """Verifies end-to-end batch generation with safe filters and optional fields."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
    doc_type = DocumentType.objects.create(name="Приказ с фильтрами")
    uploaded_docx = SimpleUploadedFile(
        name="order.docx",
        content=make_docx_bytes(
            [
                "Сотрудник: {{ employee_name | upper }}",
                "Комментарий: {{ optional_note | default('Без примечаний', true) }}",
                "Дата: {{ current_date }}",
            ]
        ),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    template = TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=uploaded_docx,
        name="Приказ v1",
        user=admin_user,
    )
    assert template.detected_variables == ["current_date", "employee_name", "optional_note"]

    data_source = DataSourceService.create_data_source(
        name="Список сотрудников",
        uploaded_file=make_uploaded_csv(
            filename="staff.csv",
            rows=[
                ["ФИО", "Примечание"],
                ["Анна Смирнова", "Срочно"],
                ["Олег Кузнецов", ""],
            ],
        ),
        user=admin_user,
    )
    mapping = MappingService.create_or_update_mapping_config(
        name="Маппинг приказа",
        template=template,
        data_source=data_source,
        rules_data=[
            {"template_variable": "employee_name", "source_column": "ФИО", "required": True},
            {
                "template_variable": "optional_note",
                "source_column": "Примечание",
                "required": False,
            },
        ],
        user=admin_user,
    )

    records = list(data_source.records.all().order_by("row_number"))
    batch = DocumentGenerationService.generate_batch(
        mapping_config=mapping,
        data_records=records,
        user=admin_user,
    )

    assert batch.status == BatchStatus.COMPLETED
    assert batch.successful_records == 2
    assert batch.failed_records == 0

    docs = list(batch.documents.order_by("id"))
    first_doc = Document(docs[0].file.path)
    second_doc = Document(docs[1].file.path)
    assert "АННА СМИРНОВА" in " ".join(p.text for p in first_doc.paragraphs)
    assert "Срочно" in " ".join(p.text for p in first_doc.paragraphs)
    assert "ОЛЕГ КУЗНЕЦОВ" in " ".join(p.text for p in second_doc.paragraphs)
    assert "Без примечаний" in " ".join(p.text for p in second_doc.paragraphs)

    with zipfile.ZipFile(batch.output_file.path, "r") as zf:
        assert len(zf.namelist()) == 2

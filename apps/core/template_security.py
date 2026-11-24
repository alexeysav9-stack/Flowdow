"""Unified Jinja2 sandbox configuration and strict AST validation for DOCX templates."""

import builtins
import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _
from docxtpl import DocxTemplate
from jinja2 import Undefined, meta, nodes
from jinja2.exceptions import SecurityError, TemplateError, TemplateSyntaxError
from jinja2.filters import FILTERS as JINJA_DEFAULT_FILTERS
from jinja2.lexer import (
    TOKEN_BLOCK_BEGIN,
    TOKEN_BLOCK_END,
    TOKEN_LINECOMMENT,
    TOKEN_LINECOMMENT_BEGIN,
    TOKEN_LINECOMMENT_END,
    TOKEN_LINESTATEMENT_BEGIN,
    TOKEN_LINESTATEMENT_END,
    TOKEN_RAW_BEGIN,
    TOKEN_RAW_END,
)
from jinja2.sandbox import ImmutableSandboxedEnvironment

VALID_IDENTIFIER_REGEX = re.compile(r"^[^\W\d]\w*$")

MAX_AST_DEPTH = 32
MAX_AST_NODES = 100_000
MAX_CONST_STRING_LENGTH = 2_000

FOOTNOTES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
)
CORE_PROPERTY_FIELDS: tuple[str, ...] = (
    "author",
    "comments",
    "identifier",
    "language",
    "subject",
    "title",
)

FORBIDDEN_TOKEN_TYPES: frozenset[str] = frozenset(
    {
        TOKEN_BLOCK_BEGIN,
        TOKEN_BLOCK_END,
        TOKEN_LINESTATEMENT_BEGIN,
        TOKEN_LINESTATEMENT_END,
        TOKEN_LINECOMMENT_BEGIN,
        TOKEN_LINECOMMENT_END,
        TOKEN_LINECOMMENT,
        TOKEN_RAW_BEGIN,
        TOKEN_RAW_END,
    }
)

# Jinja2 globals, context helpers, and sensitive Python/system names never allowed as variables.
FORBIDDEN_IDENTIFIERS: frozenset[str] = frozenset(vars(builtins).keys()) | frozenset(
    {
        "cycler",
        "joiner",
        "lipsum",
        "namespace",
        "range",
        "dict",
        "self",
        "loop",
        "super",
        "varargs",
        "kwargs",
        "caller",
        "true",
        "false",
        "none",
        "os",
        "sys",
        "subprocess",
        "importlib",
        "builtins",
        "ctypes",
        "socket",
        "pathlib",
        "shutil",
        "pickle",
        "marshal",
        "codecs",
        "operator",
        "inspect",
        "traceback",
        "gc",
        "types",
        "config",
        "request",
        "session",
        "g",
        "url_for",
        "get_flashed_messages",
    }
)


@dataclass(frozen=True)
class FilterSpec:
    """Strict argument specification for an allowlisted Jinja2 filter."""

    max_args: int
    allowed_kwargs: frozenset[str] = frozenset()


ALLOWED_FILTER_SPECS: dict[str, FilterSpec] = {
    "upper": FilterSpec(max_args=0),
    "lower": FilterSpec(max_args=0),
    "capitalize": FilterSpec(max_args=0),
    "title": FilterSpec(max_args=0),
    "trim": FilterSpec(max_args=1, allowed_kwargs=frozenset({"chars"})),
    "default": FilterSpec(max_args=2, allowed_kwargs=frozenset({"default_value", "boolean"})),
    "d": FilterSpec(max_args=2, allowed_kwargs=frozenset({"default_value", "boolean"})),
    "replace": FilterSpec(max_args=3, allowed_kwargs=frozenset({"old", "new", "count"})),
}


class TemplateSecurityError(SecurityError):
    """Raised when a DOCX template contains disallowed or dangerous Jinja2 syntax.

    Messages must remain generic and never expose tracebacks, filesystem paths, or internals.
    """


def validate_template_identifier(name: str) -> str:
    """Validates that a template variable name is a safe, non-private, non-builtin identifier."""
    if not isinstance(name, str) or not name:
        raise TemplateSecurityError(_("Шаблон содержит недопустимый идентификатор переменной."))

    # Reject Unicode compatibility homoglyphs (e.g. mathematical bold '𝐜𝐲𝐜𝐥𝐞𝐫' or fullwidth '_').
    if unicodedata.normalize("NFC", name) != unicodedata.normalize("NFKC", name):
        raise TemplateSecurityError(
            _("Шаблон содержит недопустимые Unicode-символы в имени переменной.")
        )

    if name.startswith("_"):
        raise TemplateSecurityError(
            _("Шаблон содержит запрещённое обращение к приватному или служебному имени.")
        )

    if not name.isidentifier() or not VALID_IDENTIFIER_REGEX.match(name):
        raise TemplateSecurityError(_("Шаблон содержит некорректное имя переменной."))

    if name in FORBIDDEN_IDENTIFIERS:
        raise TemplateSecurityError(
            _("Шаблон использует запрещённое зарезервированное имя объекта или модуля.")
        )

    return name


def validate_jinja_tokens(env: "SafeDocxJinjaEnvironment", source: str) -> None:
    """Rejects statement blocks, raw blocks, and line statements before AST parsing."""
    for _lineno, token_type, _value in env.lexer.tokeniter(source, None, None):
        if token_type in FORBIDDEN_TOKEN_TYPES:
            raise TemplateSecurityError(
                _("Шаблон содержит неподдерживаемые управляющие блоки или директивы Jinja2.")
            )


def _validate_ast_node(node: nodes.Node, depth: int, state: dict[str, int]) -> None:
    """Recursively validates a Jinja2 AST node against a strict allowlist."""
    if depth > MAX_AST_DEPTH:
        raise TemplateSecurityError(
            _("Превышена допустимая глубина вложенности выражений в шаблоне.")
        )

    state["count"] += 1
    if state["count"] > MAX_AST_NODES:
        raise TemplateSecurityError(_("Превышен допустимый объём выражений в шаблоне."))

    node_type = type(node)

    if node_type is nodes.Template:
        if depth != 0 or not isinstance(node.body, list):
            raise TemplateSecurityError(_("Недопустимая структура AST шаблона."))
        for child in node.body:
            if type(child) is not nodes.Output:
                raise TemplateSecurityError(
                    _("Шаблон может содержать только текст и подстановки переменных.")
                )
            _validate_ast_node(child, depth + 1, state)
        return

    if node_type is nodes.Output:
        if not isinstance(node.nodes, list):
            raise TemplateSecurityError(_("Недопустимая структура вывода в шаблоне."))
        for child in node.nodes:
            _validate_ast_node(child, depth + 1, state)
        return

    if node_type is nodes.TemplateData:
        return

    if node_type is nodes.Name:
        if node.ctx != "load":
            raise TemplateSecurityError(
                _("Присваивание и изменение переменных в шаблоне запрещено.")
            )
        validate_template_identifier(node.name)
        return

    if node_type is nodes.Const:
        if type(node.value) not in (str, int, float, bool, type(None)):
            raise TemplateSecurityError(_("Недопустимый тип константы в шаблоне."))
        if isinstance(node.value, str) and len(node.value) > MAX_CONST_STRING_LENGTH:
            raise TemplateSecurityError(_("Превышена допустимая длина строковой константы."))
        return

    if node_type is nodes.Filter:
        if node.node is None:
            raise TemplateSecurityError(_("Блочные фильтры в шаблоне запрещены."))
        spec = ALLOWED_FILTER_SPECS.get(node.name)
        if spec is None:
            raise TemplateSecurityError(
                _("Шаблон использует запрещённый или неподдерживаемый фильтр Jinja2.")
            )
        if node.dyn_args is not None or node.dyn_kwargs is not None:
            raise TemplateSecurityError(_("Распаковка аргументов в фильтрах шаблона запрещена."))
        if len(node.args) > spec.max_args:
            raise TemplateSecurityError(_("Недопустимое количество аргументов фильтра в шаблоне."))
        _validate_ast_node(node.node, depth + 1, state)
        for arg in node.args:
            _validate_ast_node(arg, depth + 1, state)
        for kw in node.kwargs:
            if type(kw) is not nodes.Keyword or kw.key not in spec.allowed_kwargs:
                raise TemplateSecurityError(
                    _("Недопустимый именованный аргумент фильтра в шаблоне.")
                )
            _validate_ast_node(kw.value, depth + 1, state)
        return

    raise TemplateSecurityError(
        _("Шаблон содержит запрещённое или неподдерживаемое выражение Jinja2.")
    )


def validate_jinja_ast(ast: nodes.Template) -> None:
    """Validates an entire parsed Jinja2 Template AST against the strict allowlist."""
    if type(ast) is not nodes.Template:
        raise TemplateSecurityError(_("Недопустимый корневой узел шаблона."))
    _validate_ast_node(ast, depth=0, state={"count": 0})


class SafeDocxJinjaEnvironment(ImmutableSandboxedEnvironment):
    """Hardened Jinja2 environment enforcing AST allowlisting and stripping globals/filters."""

    def __init__(self) -> None:
        super().__init__(
            block_start_string="{%",
            block_end_string="%}",
            variable_start_string="{{",
            variable_end_string="}}",
            comment_start_string="{#",
            comment_end_string="#}",
            line_statement_prefix=None,
            line_comment_prefix=None,
            extensions=(),
            optimized=True,
            undefined=Undefined,
            finalize=None,
            autoescape=False,
            loader=None,
            cache_size=0,
            auto_reload=False,
            bytecode_cache=None,
            enable_async=False,
        )
        self.globals.clear()
        self.filters = {name: JINJA_DEFAULT_FILTERS[name] for name in ALLOWED_FILTER_SPECS}
        self.tests.clear()

    def add_extension(self, extension: Any) -> None:
        raise TemplateSecurityError(_("Расширения Jinja2 отключены политикой безопасности."))

    def overlay(self, *args: Any, **kwargs: Any) -> Any:
        raise TemplateSecurityError(
            _("Модификация защищённой среды выполнения шаблонов запрещена.")
        )

    def is_safe_attribute(self, obj: Any, attr: str, value: Any) -> bool:
        return False

    def is_safe_callable(self, obj: Any) -> bool:
        return False

    def getattr(self, obj: Any, attribute: str) -> Any:
        raise TemplateSecurityError(_("Доступ к атрибутам объектов в шаблоне запрещён."))

    def getitem(self, obj: Any, argument: Any) -> Any:
        raise TemplateSecurityError(_("Индексный доступ к объектам в шаблоне запрещён."))

    def _parse(self, source: str, name: str | None, filename: str | None) -> nodes.Template:
        validate_jinja_tokens(self, source)
        ast = super()._parse(source, name, filename)
        validate_jinja_ast(ast)
        return ast

    def compile(
        self,
        source: str | nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: bool = False,
        defer_init: bool = False,
    ) -> Any:
        if isinstance(source, nodes.Template):
            validate_jinja_ast(source)
        return super().compile(
            source,
            name=name,
            filename=filename,
            raw=raw,
            defer_init=defer_init,
        )


def create_safe_jinja_environment() -> SafeDocxJinjaEnvironment:
    """Factory returning a fresh, hardened Jinja2 environment for DOCX inspection and rendering."""
    return SafeDocxJinjaEnvironment()


def _normalize_xml_for_jinja(doc: DocxTemplate, raw_xml: str) -> str:
    """Applies the exact XML preprocessing used by docxtpl before Jinja2 parsing."""
    patched = doc.patch_xml(raw_xml)
    return re.sub(r"<w:p([ >])", r"\n<w:p\1", patched)


def extract_docx_jinja_sources(doc: DocxTemplate) -> list[str]:
    """Extracts every template string from a DOCX that DocxTemplate.render() evaluates."""
    doc.init_docx()
    sources: list[str] = []

    # 1. Main document body
    sources.append(_normalize_xml_for_jinja(doc, doc.get_xml()))

    # 2. Headers and footers
    for uri in (doc.HEADER_URI, doc.FOOTER_URI):
        for _rel_key, part in doc.get_headers_footers(uri):
            sources.append(_normalize_xml_for_jinja(doc, doc.get_part_xml(part)))

    # 3. Footnotes
    seen_footnote_parts: set[int] = set()
    for section in doc.docx.sections:
        for part in section.part.package.parts:
            if part.content_type == FOOTNOTES_CONTENT_TYPE and id(part) not in seen_footnote_parts:
                seen_footnote_parts.add(id(part))
                raw_blob = part.blob.decode("utf-8") if isinstance(part.blob, bytes) else part.blob
                sources.append(_normalize_xml_for_jinja(doc, raw_blob))

    # 4. Core properties (evaluated by DocxTemplate.render_properties)
    for prop in CORE_PROPERTY_FIELDS:
        value = getattr(doc.docx.core_properties, prop, "")
        if isinstance(value, str) and value:
            sources.append(value)

    return sources


def inspect_and_validate_docx(
    doc: DocxTemplate,
    jinja_env: SafeDocxJinjaEnvironment | None = None,
) -> list[str]:
    """Validates all Jinja2 expressions in a DOCX and returns sorted template variable names."""
    env = jinja_env if jinja_env is not None else create_safe_jinja_environment()
    variables: set[str] = set()

    for source in extract_docx_jinja_sources(doc):
        ast = env.parse(source)
        for var in meta.find_undeclared_variables(ast):
            variables.add(validate_template_identifier(var))

    return sorted(variables)


def render_docx_safely(template_source: Any, context: dict[str, Any]) -> io.BytesIO:
    """Validates and renders a DOCX template inside the hardened Jinja2 environment."""
    safe_env = create_safe_jinja_environment()
    doc = DocxTemplate(template_source)
    inspect_and_validate_docx(doc, jinja_env=safe_env)
    doc.render(context, jinja_env=safe_env, autoescape=False)
    output_stream = io.BytesIO()
    doc.save(output_stream)
    output_stream.seek(0)
    return output_stream


__all__ = [
    "ALLOWED_FILTER_SPECS",
    "FORBIDDEN_IDENTIFIERS",
    "SafeDocxJinjaEnvironment",
    "TemplateError",
    "TemplateSecurityError",
    "TemplateSyntaxError",
    "create_safe_jinja_environment",
    "extract_docx_jinja_sources",
    "inspect_and_validate_docx",
    "render_docx_safely",
    "validate_jinja_ast",
    "validate_template_identifier",
]

"""Tests for mapping configuration, validation rules, and system variables."""

import pytest

from apps.data_sources.services import DataSourceService
from apps.documents.models import DocumentType
from apps.mapping.services import (
    MappingService,
    MappingValidationService,
    get_system_variables,
)
from apps.templates_manager.models import Template, TemplateStatus
from apps.templates_manager.services import TemplateService
from tests.conftest import make_uploaded_csv, make_uploaded_docx


@pytest.fixture
def active_template(db) -> Template:
    """Creates a document type with an active template."""
    doc_type = DocumentType.objects.create(name="Справка об обучении")
    uploaded_docx = make_uploaded_docx(
        filename="spravka.docx",
        paragraphs=["Студент {{ full_name }} обучается в группе {{ group }} с {{ current_date }}."],
    )
    return TemplateService.create_template_version(
        document_type=doc_type,
        file_obj=uploaded_docx,
        name="Шаблон справки 2026",
    )


@pytest.fixture
def ready_data_source(db, admin_user):
    """Creates a ready data source."""
    uploaded_csv = make_uploaded_csv(
        filename="students.csv",
        rows=[
            ["ФИО", "Группа", "Специальность"],
            ["Иванов Иван", "ИС-21", "Разработка ПО"],
            ["Петров Петр", "ИС-22", "Сетевое администрирование"],
        ],
    )
    return DataSourceService.create_data_source(
        name="Студенты",
        uploaded_file=uploaded_csv,
        user=admin_user,
    )


@pytest.mark.django_db
def test_create_mapping_config_and_rules(active_template, ready_data_source, admin_user):
    """Verifies creating a MappingConfig and linked MappingRules."""
    rules_data = [
        {"template_variable": "full_name", "source_column": "ФИО", "required": True},
        {"template_variable": "group", "source_column": "Группа", "required": True},
        {
            "template_variable": "current_date",
            "source_column": "",
            "default_value": "",
            "required": False,
        },
    ]

    config = MappingService.create_or_update_mapping_config(
        name="Маппинг справки",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    assert config.pk is not None
    assert config.name == "Маппинг справки"
    assert config.rules.count() == 3

    rules_dict = config.get_rules_dict()
    assert "full_name" in rules_dict
    assert rules_dict["full_name"]["source_column"] == "ФИО"
    assert rules_dict["full_name"]["required"] is True


@pytest.mark.django_db
def test_validate_mapping_config_success(active_template, ready_data_source, admin_user):
    """Verifies that a fully covered active mapping passes validation."""
    rules_data = [
        {"template_variable": "full_name", "source_column": "ФИО", "required": True},
        {"template_variable": "group", "source_column": "Группа", "required": True},
        {"template_variable": "current_date", "source_column": "", "required": False},
    ]
    config = MappingService.create_or_update_mapping_config(
        name="Корректная схема",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    is_valid, errors = MappingValidationService.validate_mapping_config(config)
    assert is_valid is True
    assert len(errors) == 0


@pytest.mark.django_db
def test_validate_mapping_config_rejects_inactive_template(
    active_template, ready_data_source, admin_user
):
    """Verifies that inactive template status is caught during validation."""
    active_template.status = TemplateStatus.ARCHIVED
    active_template.save()

    rules_data = [
        {"template_variable": "full_name", "source_column": "ФИО", "required": True},
        {"template_variable": "group", "source_column": "Группа", "required": True},
    ]
    config = MappingService.create_or_update_mapping_config(
        name="Схема с архивным шаблоном",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    is_valid, errors = MappingValidationService.validate_mapping_config(config)
    assert is_valid is False
    assert any("не активен" in err for err in errors)


@pytest.mark.django_db
def test_validate_mapping_config_missing_column(active_template, ready_data_source, admin_user):
    """Verifies error detection when variable is mapped to non-existent column."""
    rules_data = [
        {
            "template_variable": "full_name",
            "source_column": "НесуществующаяКолонка",
            "required": True,
        },
        {"template_variable": "group", "source_column": "Группа", "required": True},
    ]
    config = MappingService.create_or_update_mapping_config(
        name="Схема с неверной колонкой",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    is_valid, errors = MappingValidationService.validate_mapping_config(config)
    assert is_valid is False
    assert any("отсутствующей в источнике колонкой" in err for err in errors)


@pytest.mark.django_db
def test_validate_mapping_config_unmapped_required_variable(
    active_template, ready_data_source, admin_user
):
    """Verifies error when required template variable has neither column nor default value."""
    rules_data = [
        {
            "template_variable": "full_name",
            "source_column": "",
            "default_value": "",
            "required": True,
        },
        {"template_variable": "group", "source_column": "Группа", "required": True},
    ]
    config = MappingService.create_or_update_mapping_config(
        name="Схема без значения",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    is_valid, errors = MappingValidationService.validate_mapping_config(config)
    assert is_valid is False
    assert any("не имеет привязки к колонке или значения по умолчанию" in err for err in errors)


@pytest.mark.django_db
def test_build_record_context_system_and_default_values(
    active_template, ready_data_source, admin_user
):
    """Verifies context construction with column mapping, default values, and system variables."""
    rules_data = [
        {"template_variable": "full_name", "source_column": "ФИО", "required": True},
        {
            "template_variable": "group",
            "source_column": "",
            "default_value": "Группа-По-Умолчанию",
            "required": True,
        },
    ]
    config = MappingService.create_or_update_mapping_config(
        name="Схема с дефолтом",
        template=active_template,
        data_source=ready_data_source,
        rules_data=rules_data,
        user=admin_user,
    )

    row_data = {"ФИО": "Сидоров Сидор"}
    context, errors = MappingValidationService.build_record_context(config, row_data, row_number=1)

    assert len(errors) == 0
    assert context["full_name"] == "Сидоров Сидор"
    assert context["group"] == "Группа-По-Умолчанию"
    # System variable automatically resolved
    assert "current_date" in context
    assert len(context["current_date"]) == 10  # DD.MM.YYYY


def test_system_variables_provider():
    """Verifies safe system variables generation without code execution."""
    sys_vars = get_system_variables()
    assert "current_date" in sys_vars
    assert "current_datetime" in sys_vars
    assert "current_year" in sys_vars
    assert sys_vars["system_platform"] == "Flowdow"

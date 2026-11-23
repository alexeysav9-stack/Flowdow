"""Service layer for variable mapping, data validation, and system variables."""

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import UserRole
from apps.audit.services import AuditService
from apps.data_sources.models import DataSource, DataSourceStatus
from apps.mapping.models import MappingConfig, MappingRule
from apps.templates_manager.models import Template, TemplateStatus

UserModel = get_user_model()


class MappingValidationError(Exception):
    """Raised when mapping configuration or record data fails validation."""

    pass


def can_manage_mappings(user: Any) -> bool:
    """Checks whether the user has rights to configure or edit mappings."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    user_role = getattr(user, "role", None)
    return user_role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR}


class MappingPermissionMixin(UserPassesTestMixin):
    """View mixin enforcing mapping modification rights."""

    def test_func(self) -> bool:
        return can_manage_mappings(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(
            _("У вашей роли недостаточно прав для создания или изменения схем сопоставления.")
        )


def get_system_variables(extra_context: dict[str, Any] | None = None) -> dict[str, str]:
    """Generates standard, safe system variables available to any template.

    Never executes arbitrary user code or allows system shell access.
    """
    now = timezone.now()
    system_vars = {
        "current_date": now.strftime("%d.%m.%Y"),
        "current_date_iso": now.strftime("%Y-%m-%d"),
        "current_datetime": now.strftime("%d.%m.%Y %H:%M"),
        "current_datetime_iso": now.strftime("%Y-%m-%d %H:%M:%S"),
        "current_year": str(now.year),
        "current_month": f"{now.month:02d}",
        "current_day": f"{now.day:02d}",
        "system_platform": "Flowdow",
    }
    if extra_context:
        system_vars.update(extra_context)
    return system_vars


class MappingValidationService:
    """Validates mapping configurations and builds verified record contexts."""

    @classmethod
    def validate_rules(
        cls,
        template_variables: list[str],
        mapping_rules: dict[str, dict],
        data_columns: list[str],
    ) -> tuple[bool, list[str]]:
        """Backwards-compatible rule validation.

        Returns (is_valid, list_of_error_messages).
        """
        errors = []
        available_columns = set(data_columns)
        system_vars = get_system_variables()

        for var in template_variables:
            if var in system_vars and var not in mapping_rules:
                # System variable automatically resolved
                continue

            rule = mapping_rules.get(var)
            if not rule:
                errors.append(f"Variable '{var}' has no assigned mapping rule.")
                continue

            target_col = rule.get("column") or rule.get("source_column")
            default_val = rule.get("default") or rule.get("default_value")
            is_required = rule.get("required", True)

            if target_col and target_col not in available_columns:
                errors.append(f"Variable '{var}' maps to unknown column '{target_col}'.")
            elif not target_col and not default_val and is_required:
                if var in system_vars:
                    continue
                errors.append(
                    f"Required variable '{var}' has neither a column mapping nor a default value."
                )

        return len(errors) == 0, errors

    @classmethod
    def validate_mapping_config(cls, mapping_config: MappingConfig) -> tuple[bool, list[str]]:
        """Performs complete validation on a MappingConfig.

        Returns (is_valid, list_of_errors).
        """
        errors: list[str] = []
        template = mapping_config.template
        data_source = mapping_config.data_source

        # 1. Template checks
        if not template:
            errors.append(_("В конфигурации маппинга отсутствует ссылка на шаблон."))
            return False, errors

        if template.status != TemplateStatus.ACTIVE:
            errors.append(
                _("Шаблон «%(name)s» v%(ver)d не активен (текущий статус: %(status)s).")
                % {
                    "name": template.name,
                    "ver": template.version,
                    "status": template.get_status_display(),
                }
            )

        if not template.file:
            errors.append(_("Файл шаблона отсутствует."))

        # 2. DataSource checks
        if not data_source:
            errors.append(_("В конфигурации маппинга отсутствует источник данных."))
            return False, errors

        if data_source.status != DataSourceStatus.READY:
            errors.append(
                _(
                    "Источник данных «%(name)s» не готов к использованию (текущий статус: %(status)s)."
                )
                % {"name": data_source.name, "status": data_source.get_status_display()}
            )

        # 3. Variable coverage checks
        rules_dict = mapping_config.get_rules_dict()
        available_columns = set(data_source.headers)
        system_vars = get_system_variables()

        for var in template.detected_variables:
            if var in system_vars and var not in rules_dict:
                continue

            rule = rules_dict.get(var)
            if not rule:
                errors.append(
                    _("Переменная шаблона «%(var)s» не имеет настроенного правила маппинга.")
                    % {"var": var}
                )
                continue

            src_col = rule.get("source_column", "").strip()
            def_val = rule.get("default_value", "").strip()
            is_req = rule.get("required", True)

            if src_col and src_col not in available_columns:
                errors.append(
                    _(
                        "Переменная «%(var)s» сопоставлена с отсутствующей в источнике колонкой «%(col)s»."
                    )
                    % {"var": var, "col": src_col}
                )
            elif not src_col and not def_val and is_req:
                if var in system_vars:
                    continue
                errors.append(
                    _(
                        "Обязательная переменная «%(var)s» не имеет привязки к колонке или значения по умолчанию."
                    )
                    % {"var": var}
                )

        return len(errors) == 0, errors

    @classmethod
    def build_record_context(
        cls,
        mapping_config: MappingConfig,
        record_data: dict[str, Any],
        row_number: int = 1,
    ) -> tuple[dict[str, Any], list[str]]:
        """Constructs rendering context for a single record row.

        Returns (context_dict, list_of_errors).
        """
        errors: list[str] = []
        context: dict[str, Any] = get_system_variables()
        rules_dict = mapping_config.get_rules_dict()
        template_vars = mapping_config.template.detected_variables

        for var in template_vars:
            rule = rules_dict.get(var)
            if not rule:
                if var in context:
                    # Satisfied by system variable
                    continue
                errors.append(
                    _("Строка %(row)d: отсутствует правило для переменной «%(var)s».")
                    % {"row": row_number, "var": var}
                )
                continue

            src_col = rule.get("source_column", "").strip()
            def_val = rule.get("default_value", "").strip()
            is_req = rule.get("required", True)

            val = ""
            if src_col:
                raw_val = record_data.get(src_col, "")
                val = str(raw_val).strip() if raw_val is not None else ""

            if not val and def_val:
                val = def_val

            if not val and var in context:
                val = context[var]

            if not val and is_req:
                errors.append(
                    _(
                        "Строка %(row)d: обязательное поле «%(var)s» (колонка «%(col)s») не заполнено."
                    )
                    % {"row": row_number, "var": var, "col": src_col or _("по умолчанию")}
                )

            context[var] = val

        return context, errors


class MappingService:
    """Service managing MappingConfig and MappingRule entities."""

    @classmethod
    def create_or_update_mapping_config(
        cls,
        name: str,
        template: Template,
        data_source: DataSource,
        rules_data: list[dict[str, Any]],
        user: Any | None = None,
        description: str = "",
        config_id: int | None = None,
    ) -> MappingConfig:
        """Saves a MappingConfig and its associated MappingRules in an atomic transaction."""
        with transaction.atomic():
            if config_id:
                mapping_config = MappingConfig.objects.get(pk=config_id)
                mapping_config.name = name
                mapping_config.template = template
                mapping_config.data_source = data_source
                mapping_config.description = description
                mapping_config.save()
                mapping_config.rules.all().delete()
            else:
                mapping_config = MappingConfig.objects.create(
                    name=name,
                    template=template,
                    data_source=data_source,
                    description=description,
                    created_by=user
                    if (user and getattr(user, "is_authenticated", False))
                    else None,
                )

            # Persist MappingRules
            rules_to_create = []
            for item in rules_data:
                var_name = item.get("template_variable", "").strip()
                if not var_name:
                    continue
                rules_to_create.append(
                    MappingRule(
                        mapping_config=mapping_config,
                        template_variable=var_name,
                        source_column=item.get("source_column", "").strip(),
                        default_value=item.get("default_value", "").strip(),
                        required=bool(item.get("required", True)),
                    )
                )

            if rules_to_create:
                MappingRule.objects.bulk_create(rules_to_create)

        AuditService.log(
            action="MAPPING_CONFIG_SAVED",
            resource_type="MappingConfig",
            resource_id=str(mapping_config.id),
            user=user,
            details={
                "name": mapping_config.name,
                "template": template.name,
                "data_source": data_source.name,
                "rules_count": len(rules_to_create),
            },
        )
        return mapping_config

    @classmethod
    def delete_mapping_config(cls, config_id: int, user: Any | None = None) -> bool:
        """Deletes a MappingConfig with audit trail."""
        config = MappingConfig.objects.filter(pk=config_id).first()
        if not config:
            return False

        name = config.name
        with transaction.atomic():
            config.delete()

        AuditService.log(
            action="MAPPING_CONFIG_DELETED",
            resource_type="MappingConfig",
            resource_id=str(config_id),
            user=user,
            details={"name": name},
        )
        return True

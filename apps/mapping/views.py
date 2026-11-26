"""Views for Field Mapping module."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.core.permissions import (
    can_delete_mapping_config,
    can_view_data_source,
    can_view_mapping_config,
    require_permission,
    scope_mapping_configs,
)
from apps.data_sources.models import DataSource, DataSourceStatus
from apps.mapping.forms import MappingConfigForm
from apps.mapping.models import MappingConfig
from apps.mapping.services import (
    MappingPermissionMixin,
    MappingService,
    MappingValidationService,
    get_system_variables,
)
from apps.templates_manager.models import Template, TemplateStatus


class MappingListView(LoginRequiredMixin, MappingPermissionMixin, View):
    """Lists existing field mapping configurations."""

    def get(self, request: HttpRequest) -> HttpResponse:
        mappings = scope_mapping_configs(
            MappingConfig.objects.select_related(
                "template", "data_source", "template__document_type", "created_by"
            )
            .prefetch_related("rules")
            .all(),
            request.user,
        ).order_by("-created_at")
        return render(
            request,
            "mapping/list.html",
            {
                "title": _("Схемы сопоставления полей"),
                "active_nav": "mapping",
                "mappings": mappings,
            },
        )


class MappingCreateView(LoginRequiredMixin, MappingPermissionMixin, View):
    """Wizard for configuring template variable to data source column rules."""

    def get(self, request: HttpRequest) -> HttpResponse:
        template_id = request.GET.get("template_id")
        data_source_id = request.GET.get("data_source_id")
        name = request.GET.get("name", "").strip()
        description = request.GET.get("description", "").strip()

        selected_template = None
        selected_data_source = None

        if template_id and str(template_id).isdigit():
            selected_template = Template.objects.filter(
                pk=int(template_id), status=TemplateStatus.ACTIVE
            ).first()

        if data_source_id and str(data_source_id).isdigit():
            ds_candidate = DataSource.objects.filter(pk=int(data_source_id)).first()
            if ds_candidate is not None:
                require_permission(
                    can_view_data_source(request.user, ds_candidate),
                    _("Недостаточно прав для использования выбранного источника данных."),
                )
                if ds_candidate.status == DataSourceStatus.READY:
                    selected_data_source = ds_candidate

        if not name and selected_template and selected_data_source:
            doc_type_name = getattr(
                getattr(selected_template, "document_type", None), "name", selected_template.name
            )
            name = str(
                _("Маппинг: %(doc_type)s — %(data_source)s")
                % {
                    "doc_type": doc_type_name,
                    "data_source": selected_data_source.name,
                }
            )

        form = MappingConfigForm(
            initial={
                "name": name,
                "description": description,
                "template": selected_template,
                "data_source": selected_data_source,
            },
            user=request.user,
        )

        template_variables = selected_template.detected_variables if selected_template else []
        data_columns = selected_data_source.headers if selected_data_source else []
        system_vars = get_system_variables()

        variable_rows = []
        for var in template_variables:
            is_sys = var in system_vars
            variable_rows.append(
                {
                    "name": var,
                    "is_system": is_sys,
                    "source_column": var if var in data_columns else "",
                    "default_value": "",
                    "required": not is_sys,
                }
            )

        return render(
            request,
            "mapping/create.html",
            {
                "title": _("Новая схема маппинга"),
                "active_nav": "mapping",
                "form": form,
                "selected_template": selected_template,
                "selected_data_source": selected_data_source,
                "template_variables": template_variables,
                "variable_rows": variable_rows,
                "data_columns": data_columns,
                "system_vars": system_vars,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        raw_ds_id = request.POST.get("data_source")
        if raw_ds_id and str(raw_ds_id).isdigit():
            ds_candidate = DataSource.objects.filter(pk=int(raw_ds_id)).first()
            if ds_candidate is not None:
                require_permission(
                    can_view_data_source(request.user, ds_candidate),
                    _("Недостаточно прав для использования выбранного источника данных."),
                )

        form = MappingConfigForm(request.POST, user=request.user)
        if not form.is_valid():
            template_id = request.POST.get("template")
            data_source_id = request.POST.get("data_source")

            selected_template = None
            selected_data_source = None

            if template_id and str(template_id).isdigit():
                selected_template = Template.objects.filter(
                    pk=int(template_id), status=TemplateStatus.ACTIVE
                ).first()

            if data_source_id and str(data_source_id).isdigit():
                selected_data_source = DataSource.objects.filter(
                    pk=int(data_source_id), status=DataSourceStatus.READY
                ).first()

            template_variables = selected_template.detected_variables if selected_template else []
            data_columns = selected_data_source.headers if selected_data_source else []
            system_vars = get_system_variables()

            variable_rows = []
            for var in template_variables:
                col = request.POST.get(f"col_{var}", "").strip()
                def_val = request.POST.get(f"def_{var}", "").strip()
                is_req = request.POST.get(f"req_{var}") == "on"
                variable_rows.append(
                    {
                        "name": var,
                        "is_system": var in system_vars,
                        "source_column": col,
                        "default_value": def_val,
                        "required": is_req,
                    }
                )

            return render(
                request,
                "mapping/create.html",
                {
                    "title": _("Новая схема маппинга"),
                    "active_nav": "mapping",
                    "form": form,
                    "selected_template": selected_template,
                    "selected_data_source": selected_data_source,
                    "template_variables": template_variables,
                    "variable_rows": variable_rows,
                    "data_columns": data_columns,
                    "system_vars": system_vars,
                },
            )

        template = form.cleaned_data["template"]
        data_source = form.cleaned_data["data_source"]
        name = form.cleaned_data["name"]
        description = form.cleaned_data.get("description", "")

        # Extract rules for each template variable
        rules_data: list[dict] = []
        for var in template.detected_variables:
            col = request.POST.get(f"col_{var}", "").strip()
            def_val = request.POST.get(f"def_{var}", "").strip()
            is_req = request.POST.get(f"req_{var}") == "on"

            rules_data.append(
                {
                    "template_variable": var,
                    "source_column": col,
                    "default_value": def_val,
                    "required": is_req,
                }
            )

        config = MappingService.create_or_update_mapping_config(
            name=name,
            template=template,
            data_source=data_source,
            rules_data=rules_data,
            user=request.user,
            description=description,
        )

        messages.success(
            request,
            _("Конфигурация маппинга «%(name)s» успешно сохранена.") % {"name": config.name},
        )
        return redirect("mapping:detail", pk=config.pk)


class MappingDetailView(LoginRequiredMixin, MappingPermissionMixin, View):
    """Displays detailed rule bindings and validation status for a MappingConfig."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        mapping_config = get_object_or_404(
            MappingConfig.objects.select_related(
                "template", "data_source", "template__document_type", "created_by"
            ).prefetch_related("rules"),
            pk=pk,
        )
        require_permission(
            can_view_mapping_config(request.user, mapping_config),
            _("Недостаточно прав для просмотра этой схемы маппинга."),
        )

        is_valid, validation_errors = MappingValidationService.validate_mapping_config(
            mapping_config
        )
        system_vars = get_system_variables()

        return render(
            request,
            "mapping/detail.html",
            {
                "title": mapping_config.name,
                "active_nav": "mapping",
                "mapping_config": mapping_config,
                "is_valid": is_valid,
                "validation_errors": validation_errors,
                "system_vars": system_vars,
            },
        )


class MappingDeleteView(LoginRequiredMixin, MappingPermissionMixin, View):
    """Deletes a MappingConfig."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        config = get_object_or_404(MappingConfig, pk=pk)
        require_permission(
            can_delete_mapping_config(request.user, config),
            _("Недостаточно прав для удаления этой схемы маппинга."),
        )
        name = config.name
        MappingService.delete_mapping_config(pk, user=request.user)
        messages.info(
            request,
            _("Схема маппинга «%(name)s» успешно удалена.") % {"name": name},
        )
        return redirect("mapping:list")

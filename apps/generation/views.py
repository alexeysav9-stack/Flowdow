"""Views for document generation wizard, batch execution, and history."""

import logging
import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.core.archive_security import build_safe_file_response
from apps.core.permissions import (
    can_download_generated_document,
    can_view_generation_batch,
    can_view_mapping_config,
    require_permission,
    scope_generation_batches,
    scope_mapping_configs,
)
from apps.data_sources.models import DataRecord
from apps.generation.models import GeneratedDocument, GenerationBatch
from apps.generation.services import (
    DocumentGenerationService,
    GenerationPermissionMixin,
    GenerationValidationError,
)
from apps.mapping.models import MappingConfig
from apps.mapping.services import MappingValidationService

logger = logging.getLogger(__name__)


class GenerationHistoryView(LoginRequiredMixin, GenerationPermissionMixin, View):
    """Displays history of all document generation batches."""

    def get(self, request: HttpRequest) -> HttpResponse:
        batches = scope_generation_batches(
            GenerationBatch.objects.select_related(
                "template", "data_source", "initiated_by", "mapping_config"
            ).all(),
            request.user,
        ).order_by("-created_at")
        return render(
            request,
            "generation/list.html",
            {
                "title": _("История генераций"),
                "active_nav": "generation",
                "batches": batches,
            },
        )


class GenerationWizardView(LoginRequiredMixin, GenerationPermissionMixin, View):
    """Interactive wizard for selecting mapping configuration, records, and launching generation."""

    def get(self, request: HttpRequest) -> HttpResponse:
        mapping_id = request.GET.get("mapping_id")
        selected_mapping = None
        records = []
        is_valid = True
        validation_errors = []

        mappings = scope_mapping_configs(
            MappingConfig.objects.select_related("template", "data_source").all(),
            request.user,
        ).order_by("-created_at")

        if mapping_id and str(mapping_id).isdigit():
            selected_mapping = (
                MappingConfig.objects.select_related("template", "data_source")
                .prefetch_related("rules")
                .filter(pk=int(mapping_id))
                .first()
            )
            if selected_mapping:
                require_permission(
                    can_view_mapping_config(request.user, selected_mapping),
                    _("Недостаточно прав для использования выбранной схемы маппинга."),
                )
                is_valid, validation_errors = MappingValidationService.validate_mapping_config(
                    selected_mapping
                )
                # Show first 100 records for selection
                records = selected_mapping.data_source.records.all().order_by("row_number")[:100]

        return render(
            request,
            "generation/wizard.html",
            {
                "title": _("Мастер генерации документов"),
                "active_nav": "generation",
                "mappings": mappings,
                "selected_mapping": selected_mapping,
                "records": records,
                "is_valid": is_valid,
                "validation_errors": validation_errors,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        mapping_id = request.POST.get("mapping_id")
        if not mapping_id or not str(mapping_id).isdigit():
            messages.error(request, _("Необходимо выбрать схему маппинга."))
            return redirect("generation:wizard")

        mapping_config = get_object_or_404(
            MappingConfig.objects.select_related("template", "data_source"),
            pk=int(mapping_id),
        )
        require_permission(
            can_view_mapping_config(request.user, mapping_config),
            _("Недостаточно прав для запуска генерации по выбранной схеме маппинга."),
        )

        record_ids = request.POST.getlist("record_ids")
        select_all = request.POST.get("select_all") == "1"

        if select_all or not record_ids:
            # If select all or no individual IDs chosen, take all records of the data source
            data_records = list(mapping_config.data_source.records.all().order_by("row_number"))
        else:
            valid_record_ids = [int(rid) for rid in record_ids if str(rid).isdigit()]
            data_records = list(
                DataRecord.objects.filter(
                    data_source=mapping_config.data_source,
                    pk__in=valid_record_ids,
                ).order_by("row_number")
            )

        if not data_records:
            messages.error(request, _("Не выбрано ни одной строки данных для генерации."))
            return redirect(f"{redirect('generation:wizard').url}?mapping_id={mapping_id}")

        try:
            batch = DocumentGenerationService.generate_batch(
                mapping_config=mapping_config,
                data_records=data_records,
                user=request.user,
            )
            messages.success(
                request,
                _(
                    "Пакетная генерация #%(batch_id)d завершена. Сформировано: %(success)d из %(total)d документов."
                )
                % {
                    "batch_id": batch.id,
                    "success": batch.successful_records,
                    "total": batch.total_records,
                },
            )
            return redirect("generation:detail", pk=batch.pk)
        except GenerationValidationError as err:
            messages.error(request, str(err))
            return redirect(f"{redirect('generation:wizard').url}?mapping_id={mapping_id}")
        except Exception:
            logger.exception("Unexpected error launching generation for mapping #%s", mapping_id)
            messages.error(
                request,
                _("Произошла непредвиденная ошибка при запуске генерации документов."),
            )
            return redirect(f"{redirect('generation:wizard').url}?mapping_id={mapping_id}")


class GenerationDetailView(LoginRequiredMixin, GenerationPermissionMixin, View):
    """Displays detailed batch results, generated documents, and error diagnostics."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        batch = get_object_or_404(
            GenerationBatch.objects.select_related(
                "template", "data_source", "initiated_by", "mapping_config"
            ),
            pk=pk,
        )
        require_permission(
            can_view_generation_batch(request.user, batch),
            _("Недостаточно прав для просмотра этого пакета генерации."),
        )
        documents = batch.documents.select_related("data_record").all().order_by("id")

        return render(
            request,
            "generation/detail.html",
            {
                "title": _("Пакет генерации #%(id)d") % {"id": batch.id},
                "active_nav": "generation",
                "batch": batch,
                "documents": documents,
            },
        )


class GenerationBatchDownloadView(LoginRequiredMixin, GenerationPermissionMixin, View):
    """Downloads the compiled ZIP archive of all successfully created documents."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        batch = get_object_or_404(GenerationBatch, pk=pk)
        require_permission(
            can_view_generation_batch(request.user, batch),
            _("Недостаточно прав для скачивания архива этого пакета генерации."),
        )
        filename = os.path.basename(batch.output_file.name) if batch.output_file else ""
        return build_safe_file_response(
            batch.output_file,
            download_name=filename,
            content_type="application/zip",
            not_found_message=_("Архив документов не сформирован или отсутствует на сервере."),
        )


class GeneratedDocumentDownloadView(LoginRequiredMixin, GenerationPermissionMixin, View):
    """Downloads an individual generated DOCX document."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        doc = get_object_or_404(GeneratedDocument.objects.select_related("batch"), pk=pk)
        require_permission(
            can_download_generated_document(request.user, doc),
            _("Недостаточно прав для скачивания этого документа."),
        )
        filename = os.path.basename(doc.file.name) if doc.file else ""
        return build_safe_file_response(
            doc.file,
            download_name=filename,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            not_found_message=_("Файл документа не найден на сервере."),
        )

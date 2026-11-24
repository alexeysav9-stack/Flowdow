"""Views for document generation wizard, batch execution, and history."""

import logging
import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

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


class GenerationHistoryView(LoginRequiredMixin, View):
    """Displays history of all document generation batches."""

    def get(self, request: HttpRequest) -> HttpResponse:
        batches = (
            GenerationBatch.objects.select_related(
                "template", "data_source", "initiated_by", "mapping_config"
            )
            .all()
            .order_by("-created_at")
        )
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

        mappings = MappingConfig.objects.select_related("template", "data_source").order_by(
            "-created_at"
        )

        if mapping_id and str(mapping_id).isdigit():
            selected_mapping = (
                MappingConfig.objects.select_related("template", "data_source")
                .prefetch_related("rules")
                .filter(pk=int(mapping_id))
                .first()
            )
            if selected_mapping:
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

        record_ids = request.POST.getlist("record_ids")
        select_all = request.POST.get("select_all") == "1"

        if select_all or not record_ids:
            # If select all or no individual IDs chosen, take all records of the data source
            data_records = list(mapping_config.data_source.records.all().order_by("row_number"))
        else:
            data_records = list(
                DataRecord.objects.filter(
                    data_source=mapping_config.data_source,
                    pk__in=record_ids,
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


class GenerationDetailView(LoginRequiredMixin, View):
    """Displays detailed batch results, generated documents, and error diagnostics."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        batch = get_object_or_404(
            GenerationBatch.objects.select_related(
                "template", "data_source", "initiated_by", "mapping_config"
            ),
            pk=pk,
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


class GenerationBatchDownloadView(LoginRequiredMixin, View):
    """Downloads the compiled ZIP archive of all successfully created documents."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        batch = get_object_or_404(GenerationBatch, pk=pk)
        if not batch.output_file or not os.path.exists(batch.output_file.path):
            raise Http404(_("Архив документов не сформирован или отсутствует на сервере."))

        filename = os.path.basename(batch.output_file.name)
        return FileResponse(
            open(batch.output_file.path, "rb"),
            as_attachment=True,
            filename=filename,
        )


class GeneratedDocumentDownloadView(LoginRequiredMixin, View):
    """Downloads an individual generated DOCX document."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        doc = get_object_or_404(GeneratedDocument, pk=pk)
        if not doc.file or not os.path.exists(doc.file.path):
            raise Http404(_("Файл документа не найден на сервере."))

        filename = os.path.basename(doc.file.name)
        return FileResponse(
            open(doc.file.path, "rb"),
            as_attachment=True,
            filename=filename,
        )

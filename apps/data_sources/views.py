"""Views for Data Sources module."""

import logging
import os

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.core.archive_security import build_safe_file_response
from apps.core.permissions import (
    DataSourcePermissionMixin,
    can_delete_data_source,
    can_download_data_source,
    can_view_data_source,
    require_permission,
    scope_data_sources,
)
from apps.data_sources.forms import DataSourceUploadForm
from apps.data_sources.models import DataSource
from apps.data_sources.services import (
    DataSourceService,
    DataSourceValidationError,
)

logger = logging.getLogger(__name__)


class DataSourceListView(DataSourcePermissionMixin, View):
    """Lists uploaded tabular datasets accessible to the current user."""

    def get(self, request: HttpRequest) -> HttpResponse:
        data_sources = scope_data_sources(
            DataSource.objects.select_related("uploaded_by"),
            request.user,
        ).order_by("-created_at")
        return render(
            request,
            "data_sources/list.html",
            {
                "title": _("Источники данных"),
                "active_nav": "data_sources",
                "data_sources": data_sources,
            },
        )


class DataSourceUploadView(DataSourcePermissionMixin, View):
    """Handles upload and ingestion of CSV/XLSX datasets."""

    def get(self, request: HttpRequest) -> HttpResponse:
        form = DataSourceUploadForm()
        return render(
            request,
            "data_sources/upload.html",
            {
                "title": _("Загрузка источника данных"),
                "active_nav": "data_sources",
                "form": form,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = DataSourceUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                "data_sources/upload.html",
                {
                    "title": _("Загрузка источника данных"),
                    "active_nav": "data_sources",
                    "form": form,
                },
            )

        try:
            data_source = DataSourceService.create_data_source(
                name=form.cleaned_data["name"],
                uploaded_file=request.FILES["file"],
                user=request.user,
                sheet_name=form.cleaned_data.get("sheet_name"),
                description=form.cleaned_data.get("description", ""),
            )
            messages.success(
                request,
                _(
                    "Источник данных «%(name)s» успешно импортирован. Загружено строк: %(rows)d, колонок: %(cols)d."
                )
                % {
                    "name": data_source.name,
                    "rows": data_source.row_count,
                    "cols": data_source.column_count,
                },
            )
            return redirect("data_sources:detail", pk=data_source.pk)
        except DataSourceValidationError as err:
            messages.error(request, str(err))
            return render(
                request,
                "data_sources/upload.html",
                {
                    "title": _("Загрузка источника данных"),
                    "active_nav": "data_sources",
                    "form": form,
                },
            )
        except Exception:
            logger.exception("Unexpected error during data source upload")
            messages.error(
                request,
                _("Произошла внутренняя ошибка при обработке файла данных."),
            )
            return render(
                request,
                "data_sources/upload.html",
                {
                    "title": _("Загрузка источника данных"),
                    "active_nav": "data_sources",
                    "form": form,
                },
            )


class DataSourceDetailView(DataSourcePermissionMixin, View):
    """Displays dataset details and paginated records preview."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(
            DataSource.objects.select_related("uploaded_by"),
            pk=pk,
        )
        require_permission(
            can_view_data_source(request.user, data_source),
            _("У вас нет прав на просмотр данного источника данных."),
        )
        page_number = request.GET.get("page", 1)
        records_page = DataSourceService.get_paginated_records(
            data_source, page_number=int(page_number) if str(page_number).isdigit() else 1
        )

        return render(
            request,
            "data_sources/detail.html",
            {
                "title": data_source.name,
                "active_nav": "data_sources",
                "data_source": data_source,
                "records_page": records_page,
                "headers": data_source.headers,
            },
        )


class DataSourceDeleteView(DataSourcePermissionMixin, View):
    """Deletes a DataSource along with all its DataRecords."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(DataSource, pk=pk)
        require_permission(
            can_delete_data_source(request.user, data_source),
            _("У вас нет прав на удаление данного источника данных."),
        )
        name = data_source.name
        DataSourceService.delete_data_source(data_source_id=pk, user=request.user)
        messages.info(
            request,
            _("Источник данных «%(name)s» и все связанные записи успешно удалены.")
            % {"name": name},
        )
        return redirect("data_sources:list")


class DataSourceDownloadView(DataSourcePermissionMixin, View):
    """Downloads the original uploaded data file with strict ownership enforcement."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(DataSource, pk=pk)
        require_permission(
            can_download_data_source(request.user, data_source),
            _("У вас нет прав на скачивание данного источника данных."),
        )
        filename = os.path.basename(data_source.file.name) if data_source.file else "dataset"
        content_type = (
            "text/csv"
            if filename.lower().endswith(".csv")
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return build_safe_file_response(
            data_source.file,
            download_name=filename,
            content_type=content_type,
            not_found_message=_("Файл источника данных не найден на сервере."),
        )

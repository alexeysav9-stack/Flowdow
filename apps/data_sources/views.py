"""Views for Data Sources module."""

import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.data_sources.forms import DataSourceUploadForm
from apps.data_sources.models import DataSource
from apps.data_sources.services import (
    DataSourcePermissionMixin,
    DataSourceService,
    DataSourceValidationError,
)


class DataSourceListView(LoginRequiredMixin, View):
    """Lists all uploaded tabular datasets."""

    def get(self, request: HttpRequest) -> HttpResponse:
        data_sources = (
            DataSource.objects.all().select_related("uploaded_by").order_by("-created_at")
        )
        return render(
            request,
            "data_sources/list.html",
            {
                "title": _("Источники данных"),
                "active_nav": "data_sources",
                "data_sources": data_sources,
            },
        )


class DataSourceUploadView(LoginRequiredMixin, DataSourcePermissionMixin, View):
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
        except Exception as err:
            messages.error(request, _("Ошибка обработки файла: %(err)s") % {"err": str(err)})
            return render(
                request,
                "data_sources/upload.html",
                {
                    "title": _("Загрузка источника данных"),
                    "active_nav": "data_sources",
                    "form": form,
                },
            )


class DataSourceDetailView(LoginRequiredMixin, View):
    """Displays dataset details and paginated records preview."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(
            DataSource.objects.select_related("uploaded_by"),
            pk=pk,
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


class DataSourceDeleteView(LoginRequiredMixin, DataSourcePermissionMixin, View):
    """Deletes a DataSource along with all its DataRecords."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(DataSource, pk=pk)
        name = data_source.name
        DataSourceService.delete_data_source(data_source_id=pk, user=request.user)
        messages.info(
            request,
            _("Источник данных «%(name)s» и все связанные записи успешно удалены.")
            % {"name": name},
        )
        return redirect("data_sources:list")


class DataSourceDownloadView(LoginRequiredMixin, View):
    """Downloads the original uploaded data file."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        data_source = get_object_or_404(DataSource, pk=pk)
        if not data_source.file or not os.path.exists(data_source.file.path):
            raise Http404(_("Файл источника данных не найден на сервере."))

        filename = os.path.basename(data_source.file.name)
        return FileResponse(
            open(data_source.file.path, "rb"),
            as_attachment=True,
            filename=filename,
        )

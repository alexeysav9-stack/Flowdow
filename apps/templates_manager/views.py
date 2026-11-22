"""Views for uploading, versioning, inspecting, and managing DOCX templates."""

import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.documents.models import DocumentType
from apps.documents.services import DocumentManagementPermissionMixin
from apps.templates_manager.forms import TemplateUploadForm
from apps.templates_manager.models import Template
from apps.templates_manager.services import (
    TemplateService,
    TemplateValidationError,
)


class TemplateListView(LoginRequiredMixin, View):
    """Lists all uploaded templates across all document types."""

    def get(self, request: HttpRequest) -> HttpResponse:
        templates = Template.objects.select_related("document_type").all().order_by("-created_at")
        return render(
            request,
            "templates_manager/list.html",
            {
                "title": _("Шаблоны документов"),
                "active_nav": "templates",
                "templates": templates,
            },
        )


class TemplateUploadView(LoginRequiredMixin, DocumentManagementPermissionMixin, View):
    """Handles upload and inspection of a new DOCX template version."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        doc_type = get_object_or_404(DocumentType, pk=pk)
        form = TemplateUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            # If form is invalid, re-render detail page with errors
            templates = doc_type.templates.all().order_by("-version")
            for errors in form.errors.values():
                for err in errors:
                    messages.error(request, f"{err}")
            return render(
                request,
                "documents/detail.html",
                {
                    "title": doc_type.name,
                    "active_nav": "documents",
                    "doc_type": doc_type,
                    "templates": templates,
                    "upload_form": form,
                },
            )

        uploaded_file = form.cleaned_data["file"]
        custom_name = form.cleaned_data.get("name")
        status = form.cleaned_data.get("status")
        description = form.cleaned_data.get("description", "")

        try:
            template = TemplateService.create_template_version(
                document_type=doc_type,
                file_obj=uploaded_file,
                name=custom_name,
                description=description,
                status=status,
                user=request.user,
            )

            var_count = len(template.detected_variables)
            if var_count > 0:
                var_sample = ", ".join(template.detected_variables[:5])
                if var_count > 5:
                    var_sample += f", ... (+{var_count - 5})"
                messages.success(
                    request,
                    _(
                        "Шаблон «%(name)s» v%(ver)d успешно загружен. Обнаружено переменных: %(count)d (%(sample)s)."
                    )
                    % {
                        "name": template.name,
                        "ver": template.version,
                        "count": var_count,
                        "sample": var_sample,
                    },
                )
            else:
                messages.success(
                    request,
                    _(
                        "Шаблон «%(name)s» v%(ver)d успешно загружен. В документе не обнаружено переменных."
                    )
                    % {"name": template.name, "ver": template.version},
                )

        except TemplateValidationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(
                request,
                _("Произошла непредвиденная ошибка при обработке файла: %(err)s")
                % {"err": str(exc)},
            )

        return redirect("documents:detail", pk=doc_type.pk)


class TemplateActivateView(LoginRequiredMixin, DocumentManagementPermissionMixin, View):
    """Sets a specific template version as active for its document type."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template.objects.select_related("document_type"), pk=pk)
        TemplateService.activate_template(template, user=request.user)
        messages.success(
            request,
            _("Шаблон «%(name)s» v%(ver)d активирован.")
            % {"name": template.name, "ver": template.version},
        )
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        return redirect(next_url or "documents:detail", pk=template.document_type_id)


class TemplateArchiveView(LoginRequiredMixin, DocumentManagementPermissionMixin, View):
    """Moves a template version to the archived state."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template.objects.select_related("document_type"), pk=pk)
        TemplateService.archive_template(template, user=request.user)
        messages.info(
            request,
            _("Шаблон «%(name)s» v%(ver)d перемещён в архив.")
            % {"name": template.name, "ver": template.version},
        )
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        return redirect(next_url or "documents:detail", pk=template.document_type_id)


class TemplateDownloadView(LoginRequiredMixin, View):
    """Safely downloads the DOCX template file."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template, pk=pk)
        if not template.file or not os.path.exists(template.file.path):
            raise Http404(_("Файл шаблона не найден на диске."))

        download_name = f"{template.name}_v{template.version}.docx"
        response = FileResponse(
            open(template.file.path, "rb"),
            as_attachment=True,
            filename=download_name,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return response

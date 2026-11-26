"""Views for uploading, versioning, inspecting, and managing DOCX templates."""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.core.archive_security import build_safe_file_response
from apps.core.permissions import DocumentManagementPermissionMixin, get_safe_redirect_url
from apps.documents.models import DocumentType
from apps.templates_manager.forms import TemplateUploadForm
from apps.templates_manager.models import Template
from apps.templates_manager.services import (
    TemplateService,
    TemplateValidationError,
)

logger = logging.getLogger(__name__)


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
        except Exception:
            logger.exception("Unexpected error during template upload for doc_type #%s", pk)
            messages.error(
                request,
                _("Произошла непредвиденная ошибка при обработке файла шаблона."),
            )

        return redirect("documents:detail", pk=doc_type.pk)


class TemplateActivateView(DocumentManagementPermissionMixin, View):
    """Sets a specific template version as active for its document type."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template.objects.select_related("document_type"), pk=pk)
        TemplateService.activate_template(template, user=request.user)
        messages.success(
            request,
            _("Шаблон «%(name)s» v%(ver)d активирован.")
            % {"name": template.name, "ver": template.version},
        )
        fallback_url = reverse("documents:detail", kwargs={"pk": template.document_type_id})
        target_url = get_safe_redirect_url(
            request,
            request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER"),
            fallback_url,
        )
        return redirect(target_url)


class TemplateArchiveView(DocumentManagementPermissionMixin, View):
    """Moves a template version to the archived state."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template.objects.select_related("document_type"), pk=pk)
        TemplateService.archive_template(template, user=request.user)
        messages.info(
            request,
            _("Шаблон «%(name)s» v%(ver)d перемещён в архив.")
            % {"name": template.name, "ver": template.version},
        )
        fallback_url = reverse("documents:detail", kwargs={"pk": template.document_type_id})
        target_url = get_safe_redirect_url(
            request,
            request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER"),
            fallback_url,
        )
        return redirect(target_url)


class TemplateDownloadView(DocumentManagementPermissionMixin, View):
    """Safely downloads the DOCX template file (operational roles only)."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        template = get_object_or_404(Template, pk=pk)
        download_name = f"{template.name}_v{template.version}.docx"
        return build_safe_file_response(
            template.file,
            download_name=download_name,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            not_found_message=_("Файл шаблона не найден на диске."),
        )

"""Views for managing Document Types."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.documents.forms import DocumentTypeForm
from apps.documents.models import DocumentType
from apps.documents.services import DocumentManagementPermissionMixin, DocumentTypeService
from apps.templates_manager.forms import TemplateUploadForm


class DocumentListView(LoginRequiredMixin, View):
    """Displays the catalog of all configured document types."""

    def get(self, request: HttpRequest) -> HttpResponse:
        document_types = DocumentTypeService.list_all()
        return render(
            request,
            "documents/list.html",
            {
                "title": _("Типы документов"),
                "active_nav": "documents",
                "document_types": document_types,
            },
        )


class DocumentTypeCreateView(LoginRequiredMixin, DocumentManagementPermissionMixin, View):
    """Creates a new document type category."""

    def get(self, request: HttpRequest) -> HttpResponse:
        form = DocumentTypeForm()
        return render(
            request,
            "documents/create.html",
            {
                "title": _("Новый тип документа"),
                "active_nav": "documents",
                "form": form,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = DocumentTypeForm(request.POST)
        if form.is_valid():
            doc_type = DocumentTypeService.create_document_type(
                name=form.cleaned_data["name"],
                description=form.cleaned_data.get("description", ""),
                user=request.user,
            )
            messages.success(
                request,
                _("Тип документа «%(name)s» успешно создан.") % {"name": doc_type.name},
            )
            return redirect("documents:detail", pk=doc_type.pk)

        return render(
            request,
            "documents/create.html",
            {
                "title": _("Новый тип документа"),
                "active_nav": "documents",
                "form": form,
            },
        )


class DocumentTypeDetailView(LoginRequiredMixin, View):
    """Detailed view of a DocumentType with its versioned templates history."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        doc_type = get_object_or_404(
            DocumentType.objects.prefetch_related("templates"),
            pk=pk,
        )
        templates = doc_type.templates.all().order_by("-version")
        upload_form = TemplateUploadForm()

        return render(
            request,
            "documents/detail.html",
            {
                "title": doc_type.name,
                "active_nav": "documents",
                "doc_type": doc_type,
                "templates": templates,
                "upload_form": upload_form,
            },
        )

"""URL routing for documents module."""

from django.urls import path

from apps.documents.views import (
    DocumentListView,
    DocumentTypeCreateView,
    DocumentTypeDetailView,
)
from apps.templates_manager.views import TemplateUploadView

app_name = "documents"

urlpatterns = [
    path("", DocumentListView.as_view(), name="list"),
    path("create/", DocumentTypeCreateView.as_view(), name="create"),
    path("<int:pk>/", DocumentTypeDetailView.as_view(), name="detail"),
    path("<int:pk>/templates/upload/", TemplateUploadView.as_view(), name="template_upload"),
]

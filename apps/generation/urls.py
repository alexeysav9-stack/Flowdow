"""URL routing for the Generation application."""

from django.urls import path

from apps.generation.views import (
    GeneratedDocumentDownloadView,
    GenerationBatchDownloadView,
    GenerationDetailView,
    GenerationHistoryView,
    GenerationWizardView,
)

app_name = "generation"

urlpatterns = [
    path("", GenerationHistoryView.as_view(), name="history"),
    path("list/", GenerationHistoryView.as_view(), name="list"),
    path("wizard/", GenerationWizardView.as_view(), name="wizard"),
    path("<int:pk>/", GenerationDetailView.as_view(), name="detail"),
    path("<int:pk>/download/", GenerationBatchDownloadView.as_view(), name="download_zip"),
    path(
        "document/<int:pk>/download/",
        GeneratedDocumentDownloadView.as_view(),
        name="download_doc",
    ),
]

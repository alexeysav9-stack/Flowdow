"""URL routing for templates manager module."""

from django.urls import path

from apps.templates_manager.views import (
    TemplateActivateView,
    TemplateArchiveView,
    TemplateDownloadView,
    TemplateListView,
)

app_name = "templates_manager"

urlpatterns = [
    path("", TemplateListView.as_view(), name="list"),
    path("<int:pk>/activate/", TemplateActivateView.as_view(), name="activate"),
    path("<int:pk>/archive/", TemplateArchiveView.as_view(), name="archive"),
    path("<int:pk>/download/", TemplateDownloadView.as_view(), name="download"),
]

"""URL routing for the Data Sources application."""

from django.urls import path

from apps.data_sources.views import (
    DataSourceDeleteView,
    DataSourceDetailView,
    DataSourceDownloadView,
    DataSourceListView,
    DataSourceUploadView,
)

app_name = "data_sources"

urlpatterns = [
    path("", DataSourceListView.as_view(), name="list"),
    path("upload/", DataSourceUploadView.as_view(), name="upload"),
    path("<int:pk>/", DataSourceDetailView.as_view(), name="detail"),
    path("<int:pk>/delete/", DataSourceDeleteView.as_view(), name="delete"),
    path("<int:pk>/download/", DataSourceDownloadView.as_view(), name="download"),
]

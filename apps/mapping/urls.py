"""URL routing for the Mapping application."""

from django.urls import path

from apps.mapping.views import (
    MappingCreateView,
    MappingDeleteView,
    MappingDetailView,
    MappingListView,
)

app_name = "mapping"

urlpatterns = [
    path("", MappingListView.as_view(), name="list"),
    path("create/", MappingCreateView.as_view(), name="create"),
    path("<int:pk>/", MappingDetailView.as_view(), name="detail"),
    path("<int:pk>/delete/", MappingDeleteView.as_view(), name="delete"),
]

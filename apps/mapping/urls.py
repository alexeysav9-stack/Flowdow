"""URL routing for field mapping module."""

from django.urls import path

from apps.mapping.views import MappingListView

app_name = "mapping"

urlpatterns = [
    path("", MappingListView.as_view(), name="list"),
]

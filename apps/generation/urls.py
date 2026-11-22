"""URL routing for generation module."""

from django.urls import path

from apps.generation.views import GenerationHistoryView

app_name = "generation"

urlpatterns = [
    path("", GenerationHistoryView.as_view(), name="history"),
]

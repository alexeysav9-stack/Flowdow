"""URL routing for core application."""

from django.urls import path

from apps.core.views import DashboardView, HealthCheckView

app_name = "core"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("health/", HealthCheckView.as_view(), name="health"),
]

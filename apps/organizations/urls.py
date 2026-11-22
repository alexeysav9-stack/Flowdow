"""URL routing for organization and workspace settings."""

from django.urls import path

from apps.organizations.views import OrganizationSettingsView

app_name = "organizations"

urlpatterns = [
    path("", OrganizationSettingsView.as_view(), name="settings"),
]

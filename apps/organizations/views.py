"""Views for Organization and Settings management."""

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.audit.services import AuditService
from apps.core.permissions import AdminRequiredMixin
from apps.organizations.forms import OrganizationForm, OrganizationSettingsForm
from apps.organizations.services import OrganizationService


class OrganizationSettingsView(AdminRequiredMixin, View):
    """Configuration view for organization identity and formatting settings (ADMIN only)."""

    def get(self, request: HttpRequest) -> HttpResponse:
        org = OrganizationService.get_or_create_default()
        org_form = OrganizationForm(instance=org)
        settings_form = OrganizationSettingsForm(instance=org.settings)

        return render(
            request,
            "organizations/settings.html",
            {
                "title": "Organization Settings",
                "active_nav": "settings",
                "org_form": org_form,
                "settings_form": settings_form,
                "org": org,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        org = OrganizationService.get_or_create_default()
        org_form = OrganizationForm(request.POST, instance=org)
        settings_form = OrganizationSettingsForm(request.POST, instance=org.settings)

        if org_form.is_valid() and settings_form.is_valid():
            OrganizationService.save_settings_forms(
                org_form=org_form,
                settings_form=settings_form,
                user=request.user,
            )

            AuditService.log(
                action="SETTINGS_UPDATED",
                user=request.user,
                resource_type="Organization",
                resource_id=str(org.id),
                details={"organization_name": org.name},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, "Organization settings updated successfully.")
            return redirect("organizations:settings")

        return render(
            request,
            "organizations/settings.html",
            {
                "title": "Organization Settings",
                "active_nav": "settings",
                "org_form": org_form,
                "settings_form": settings_form,
                "org": org,
            },
        )

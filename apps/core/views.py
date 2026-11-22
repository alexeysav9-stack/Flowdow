"""Core views for Dashboard and Health Monitoring."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from apps.core.services import DashboardService, HealthCheckService


class DashboardView(LoginRequiredMixin, View):
    """Main dashboard presenting operations statistics and quick actions."""

    def get(self, request: HttpRequest) -> HttpResponse:
        metrics = DashboardService.get_metrics()
        context = {
            "title": "Dashboard",
            "active_nav": "dashboard",
            **metrics,
        }
        return render(request, "core/dashboard.html", context)


class HealthCheckView(View):
    """Health check endpoint for Docker / orchestration probes."""

    def get(self, request: HttpRequest) -> JsonResponse:
        report = HealthCheckService.check_health()
        status_code = 200 if report["status"] == "healthy" else 503
        return JsonResponse(report, status=status_code)

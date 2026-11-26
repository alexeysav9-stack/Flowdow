"""Global template context processors."""

from datetime import datetime

from django.conf import settings
from django.http import HttpRequest

from apps.core.permissions import build_user_permissions_context


def global_context(request: HttpRequest) -> dict:
    """Provides application-wide variables and permission flags to all rendered templates."""
    return {
        "APP_NAME": "Flowdow",
        "APP_VERSION": "0.1.0",
        "CURRENT_YEAR": datetime.now().year,
        "ORGANIZATION_NAME": getattr(settings, "FLOWDOW_ORGANIZATION_NAME", "Flowdow Workspace"),
        "DEBUG_MODE": settings.DEBUG,
        "user_permissions": build_user_permissions_context(getattr(request, "user", None)),
    }

"""Root URL configuration for Flowdow."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("settings/", include("apps.organizations.urls")),
    path("documents/", include("apps.documents.urls")),
    path("templates/", include("apps.templates_manager.urls")),
    path("data-sources/", include("apps.data_sources.urls")),
    path("mapping/", include("apps.mapping.urls")),
    path("generation/", include("apps.generation.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

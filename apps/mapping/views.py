"""Views for Field Mapping module."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View

from apps.mapping.models import FieldMappingSchema


class MappingListView(LoginRequiredMixin, View):
    """Lists existing field mapping configurations."""

    def get(self, request: HttpRequest) -> HttpResponse:
        mappings = FieldMappingSchema.objects.select_related("template", "data_source").all()
        return render(
            request,
            "mapping/list.html",
            {
                "title": "Field Mappings",
                "active_nav": "mapping",
                "mappings": mappings,
            },
        )

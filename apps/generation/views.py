"""Views for Document Generation."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View

from apps.generation.models import GenerationBatch


class GenerationHistoryView(LoginRequiredMixin, View):
    """Displays history of all document generation batches."""

    def get(self, request: HttpRequest) -> HttpResponse:
        batches = GenerationBatch.objects.select_related(
            "template", "data_source", "initiated_by"
        ).all()
        return render(
            request,
            "generation/list.html",
            {
                "title": "Generation History",
                "active_nav": "generation",
                "batches": batches,
            },
        )

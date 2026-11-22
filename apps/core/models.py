"""Base abstract models for all Flowdow domain modules."""

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """An abstract base class model that provides self-updating

    'created_at' and 'updated_at' fields.
    """

    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name="Created At",
        help_text="Timestamp when the record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
        help_text="Timestamp when the record was last updated.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

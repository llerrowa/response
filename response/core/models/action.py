from django.db import models

from response.core.models.incident import Incident
from response.core.models.user_external import ExternalUser
from response.core.util import sanitize


class Action(models.Model):
    created_date = models.DateTimeField(null=True, auto_now_add=True)
    details = models.TextField(blank=True, default="")
    done = models.BooleanField(default=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(
        ExternalUser,
        related_name="assigned_to",
        on_delete=models.CASCADE,
        blank=False,
        null=True,
    )
    created_by = models.ForeignKey(
        ExternalUser,
        related_name="created_by",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    updated_by = models.ForeignKey(
        ExternalUser,
        related_name="edited_by",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    def icon(self):
        return "🔜️"

    def __str__(self):
        return f"{self.details}"

    def save(self, *args, **kwargs):
        self.details = sanitize(self.details)
        super(Action, self).save(*args, **kwargs)

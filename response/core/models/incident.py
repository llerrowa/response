from datetime import datetime

from django.db import models

from response import core, slack
from response.core.models.user_external import ExternalUser
from response.core.util import sanitize


class IncidentManager(models.Manager):
    def create_incident(
        self,
        name,
        reporter,
        incident_time,
        private=False,
        summary=None,
        lead=None,
        severity=None,
        updated_by=None,
        status_update=None,
        status_update_last=None,
        status_update_next=None
    ):
        incident = self.create(
            name=name,
            reporter=reporter,
            incident_time=incident_time,
            private=private,
            start_time=incident_time,
            summary=summary,
            lead=lead,
            severity=severity,
            updated_by=updated_by,
            status_update=status_update,
            status_update_last=status_update_last,
            status_update_next=status_update_next
        )
        return incident


class Incident(models.Model):

    objects = IncidentManager()

    # Reporting info
    name = models.CharField(max_length=200)
    reporter = models.ForeignKey(
        ExternalUser,
        related_name="reporter",
        on_delete=models.PROTECT,
        blank=False,
        null=True,
    )
    incident_time = models.DateTimeField()
    private = models.BooleanField(default=False)

    start_time = models.DateTimeField(null=False)
    end_time = models.DateTimeField(blank=True, null=True)

    # Additional info
    summary = models.TextField(
        blank=True, null=True, help_text="Can you share any useful details?"
    )
    lead = models.ForeignKey(
        ExternalUser,
        related_name="lead",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="Who is leading?",
    )

    updated_by = models.ForeignKey(
        ExternalUser,
        related_name="updated_by",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="Issue updated by?",
    )

    # Severity
    SEVERITIES = (("1", "critical"), ("2", "major"), ("3", "minor"))
    severity = models.CharField(
        max_length=10, blank=True, null=True, choices=SEVERITIES
    )

    status_update = models.TextField(
        blank=True, null=True, help_text="Can you provide a status update?"
    )
    status_update_last = models.DateTimeField(blank=True, null=True)
    NEXT_STATUS_UPDATE = (("5", "5 mins"), ("10", "10 mins"), ("30", "30 mins"), ("60", "1 hour"))
    status_update_next = models.CharField(
         max_length=10, blank=True, null=True, choices=NEXT_STATUS_UPDATE
    )

    def __str__(self):
        return self.name

    def comms_channel(self):
        try:
            return slack.models.CommsChannel.objects.get(incident=self)
        except slack.models.CommsChannel.DoesNotExist:
            return None

    def duration(self):
        delta = (self.end_time or datetime.now()) - self.start_time

        hours, remainder = divmod(delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)

        time_str = ""
        if hours > 0:
            hours = int(hours)
            time_str += f"{hours} hrs " if hours > 1 else f"{hours} hr "

        if minutes > 0:
            minutes = int(minutes)
            time_str += f"{minutes} mins " if minutes > 1 else f"{minutes} min "

        if hours == 0 and minutes == 0:
            seconds = int(seconds)
            time_str += f"{seconds} secs"

        return time_str.strip()

    def is_closed(self):
        return True if self.end_time else False

    def severity_text(self):
        for sev_id, text in self.SEVERITIES:
            if sev_id == self.severity:
                return text
        return None

    def severity_emoji(self):
        if not self.severity:
            return "☁️"

        return "🔥"

    def status_update_text(self):
        for update_id, text in self.NEXT_STATUS_UPDATE:
            if update_id == self.status_update_next:
                return text
        return None

    def status_text(self):
        if self.is_closed():
            return "resolved"
        else:
            return "live"

    def status_emoji(self):
        if self.is_closed():
            return "✅"
        else:
            return "🚨"

    def badge_type(self):
        if self.is_closed():
            return "badge-success"
        elif self.severity and int(self.severity) < 3:
            return "badge-danger"
        return "badge-warning"

    def action_items(self):
        return core.models.Action.objects.filter(incident=self)

    def timeline_events(self):
        return core.models.TimelineEvent.objects.filter(incident=self)

    def save(self, *args, **kwargs):
        self.name = sanitize(self.name)
        self.summary = sanitize(self.summary)
        super(Incident, self).save(*args, **kwargs)

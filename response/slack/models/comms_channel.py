import logging
from datetime import datetime
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.urls import reverse

from response.core.models.incident import Incident
from response.slack.client import SlackError

logger = logging.getLogger(__name__)


class CommsChannelManager(models.Manager):
    def create_comms_channel(self, incident: Incident, private: bool):
        """
        Creates a comms channel in slack, and saves a reference to it in the DB
        """
        time_string = datetime.now().strftime("%Y-%m-%d")
        name = f"inc-{time_string}-{incident.name.strip().replace(' ', '-')[:65]}".lower()

        try:
            channel_id = settings.SLACK_CLIENT.get_or_create_channel(
                name, auto_unarchive=True, private=private
            )
        except SlackError as e:
            logger.error(f"Failed to create comms channel {e}")
            raise

        comms_channel = self.create(
            incident=incident, channel_id=channel_id, channel_name=name
        )

        try:
            logger.info(f"Joining channel {channel_id}")
            settings.SLACK_CLIENT.invite_user_to_channel(incident.reporter.external_id, channel_id)
        except SlackError as e:
            if e.slack_error != 'already_in_channel':
                logger.error(f"Failed to join comms channel {e}")
                raise

        
        return comms_channel

    def enrich_comms_channel(self, incident: Incident, channel_id):
        try:
            settings.SLACK_CLIENT.set_channel_topic(
                channel_id, f"INCIDENT-{incident.pk}"
            )
        except SlackError as e:
            logger.error(f"Failed to set channel topic {e}")
            raise

        try:
            doc_url = urljoin(
                settings.SITE_URL,
                reverse("incident_doc", kwargs={"incident_id": incident.pk}),
            )

            settings.SLACK_CLIENT.add_channel_bookmark(
                channel_id, "Homepage", "link", doc_url, ":globe_with_meridians:"
            )
        except SlackError as e:
            logger.error(f"Failed to add channel bookmark {e}")
            raise
    
    def update_bookmarks_in_comms_channel(self, incident: Incident, channel_id):
        try:
            bookmarks = settings.SLACK_CLIENT.list_channel_bookmarks(channel_id)
            severity = incident.severity_text().upper()
            status = incident.status_text().upper()
            lead = (
                incident.lead.display_name
                if incident.lead
                else "Unassigned"
            )

            self._add_or_update_bookmarks(incident, bookmarks, channel_id, "Severity", severity, ":fire:")
            self._add_or_update_bookmarks(incident, bookmarks, channel_id, "Status", status, ":pager:")
            self._add_or_update_bookmarks(incident, bookmarks, channel_id, "Lead", lead, ":firefighter:")

        except SlackError as e:
            logger.error(f"Failed to add channel bookmark {e}")
            raise

    def _add_or_update_bookmarks(self, incident, bookmarks, channel_id, key, text, emoji):
        bookmark = next((item for item in bookmarks if item['title'].startswith(key + ":")), None)
        doc_url = urljoin(
                settings.SITE_URL,
                reverse("incident_doc", kwargs={"incident_id": incident.pk}),
            )
        if bookmark:
            bookmark_id = bookmark['id']
            settings.SLACK_CLIENT.edit_channel_bookmark(
                channel_id, bookmark_id, f"{key}: {text}", "link", doc_url, emoji
            )
        else:
            settings.SLACK_CLIENT.add_channel_bookmark(
                channel_id, f"{key}: {text}", "link", doc_url, emoji
            )    

class CommsChannel(models.Model):

    objects = CommsChannelManager()
    incident = models.OneToOneField(Incident, on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=20, null=False)
    channel_name = models.CharField(max_length=80, null=False)

    def post_in_channel(self, message: str):
        settings.SLACK_CLIENT.send_message(self.channel_id, message)

    def rename(self, new_name):
        if new_name:
            try:
                response = settings.SLACK_CLIENT.rename_channel(
                    self.channel_id, new_name
                )
                self.channel_name = response["channel"]["name"]
                self.save()
            except SlackError as e:
                logger.error(
                    f"Failed to rename channel {self.channel_id} to {new_name}. Error: {e}"
                )
                raise e
        else:
            logger.info("Attempted to rename channel to nothing. No action take.")

    def __str__(self):
        return self.incident.name

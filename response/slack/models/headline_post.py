import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.urls import reverse

from response.core.models.incident import Incident
from response.slack.block_kit import Actions, Button, Divider, Message, Section, Text, Header
from response.slack.client import SlackError
from response.slack.decorators.headline_post_action import (
    SLACK_HEADLINE_POST_ACTION_MAPPINGS,
    headline_post_action,
)
from response.slack.models.comms_channel import CommsChannel
from response.slack.reference_utils import channel_reference, user_reference

logger = logging.getLogger(__name__)


class HeadlinePostManager(models.Manager):
    def create_headline_post(self, incident):
        headline_post = self.create(incident=incident)
        headline_post.update_main_in_slack()
        return headline_post


class HeadlinePost(models.Model):

    EDIT_INCIDENT_BUTTON = "edit-incident-button"
    CLOSE_INCIDENT_BUTTON = "close-incident-button"
    OVERVIEW_INCIDENT_BUTTON = "overview-incident-button"
    REQUEST_UPDATE_INCIDENT_BUTTON = "request-update-incident-button"

    objects = HeadlinePostManager()
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE)
    message_ts = models.CharField(max_length=20, null=True)
    comms_channel = models.OneToOneField(
        CommsChannel, on_delete=models.DO_NOTHING, null=True
    )

    def update_main_in_slack(self):
        "Creates/updates the slack headline post with the latest incident info"
        logging.info(f"Updating headline post in Slack for incident {self.incident.pk}")
        mainMessage = self._create_main_message()
        channel_id = settings.INCIDENT_CHANNEL_ID

        try:
            response = mainMessage.send(channel_id, self.message_ts)
            # Save the message ts identifier if not already set
            if not self.message_ts:
                self.message_ts = response["ts"]
                self.save()
        except SlackError as e:
            logger.error(f"Failed to update headline post in {channel_id} with ts {self.message_ts}. Error: {e}")

    def _create_main_message(self):
        msg = Message()

        msg.set_fallback_text(
            f"{self.incident.name} created by {user_reference(self.incident.reporter)}"
        )

        msg.add_block(
            Header(block_id="name", text=Text(f"{self.incident.status_emoji()} {self.incident.name}", text_type="plain_text"))
        )
        if(self.incident.summary):
            msg.add_block(Section(text=Text(self.incident.summary)))            
            msg.add_block(Divider())

        msg.add_block(
            Section(
                block_id="severity",
                text=Text(
                    f"{self.incident.severity_emoji()} *Severity*: `{self.incident.severity_text().upper()}`"
                ),
            )
        )
        msg.add_block(
            Section(
                block_id="status",
                text=Text(
                    f":pager: *Status*: `{self.incident.status_text().upper()}`"
                ),
            )
        )
        msg.add_block(
            Section(
                block_id="reporter",
                text=Text(f":bust_in_silhouette: *Reporter*: {user_reference(self.incident.reporter.external_id)}")
            )
        )
        if(self.incident.lead):
            incident_lead_text = (
                user_reference(self.incident.lead.external_id)
                if self.incident.lead
                else "-"
            )
            msg.add_block(
                Section(
                    block_id="lead", text=Text(f":firefighter: *Incident Lead*: {incident_lead_text}")
                )
            )
        channel_ref = (
            channel_reference(self.comms_channel.channel_id)
            if self.comms_channel
            else None
        )
        if channel_ref:
            msg.add_block(
                Section(
                    block_id="comms_channel",
                    text=Text(f":slack: *Channel*: {channel_ref}"),
                )
            )

        msg.add_block(Divider())

        # Add buttons (if the incident is open)
        if not self.incident.is_closed():
            actions = Actions(block_id="actions")

            # Add all actions mapped by @headline_post_action decorators
            for key in sorted(SLACK_HEADLINE_POST_ACTION_MAPPINGS.keys()): 
                if(key[1]): # include_in_headline is True for action
                    funclist = SLACK_HEADLINE_POST_ACTION_MAPPINGS[key]
                    for f in funclist:
                        action = f(self.incident)
                        if action:
                            actions.add_element(action)
                

            msg.add_block(actions)
        
        return msg

    def post_to_thread(self, message):
        settings.SLACK_CLIENT.send_message(
            settings.INCIDENT_CHANNEL_ID, text=message.fallback_text, blocks=message.serialize(), thread_ts=self.message_ts
        )

# Default/core actions to display on headline post.
# In order to allow inserting actions between these ones we increment the order by 100


@headline_post_action(order=100, include_in_headline=False)
def edit_incident_button(incident):
    return Button(
        ":pencil2: Edit",
        HeadlinePost.EDIT_INCIDENT_BUTTON,
        value=incident.pk,
    )


@headline_post_action(order=200, include_in_headline=False)
def close_incident_button(incident):
    return Button(
        ":white_check_mark: Close",
        HeadlinePost.CLOSE_INCIDENT_BUTTON,
        value=incident.pk,
    )


@headline_post_action(order=300)
def overview_incident_button(incident):
    return Button(
        ":eyes: Overview",
        HeadlinePost.OVERVIEW_INCIDENT_BUTTON,
        value=incident.pk,
    )


@headline_post_action(order=400)
def request_update_incident_button(incident):
    return Button(
        ":mega: Request update",
        HeadlinePost.REQUEST_UPDATE_INCIDENT_BUTTON,
        value=incident.pk,
    )
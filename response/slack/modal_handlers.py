import logging
from datetime import datetime
from typing import Any

from response.core.models import ExternalUser, Incident
from response.slack.cache import get_user_profile
from response.slack.client import SlackError
from response.slack.decorators import modal_handler
from response.slack.decorators.headline_post_action import SLACK_HEADLINE_POST_ACTION_MAPPINGS
from response.slack.modal_builder import Modal, Section
from response.slack.models.comms_channel import CommsChannel
from response.slack.models.headline_post import HeadlinePost
from response.slack.reference_utils import user_reference
from response.slack.settings import INCIDENT_CREATE_MODAL, INCIDENT_CREATED_MODAL, INCIDENT_EDIT_MODAL, SHARE_UPDATE_MODAL, UPDATE_SUMMARY_MODAL

logger = logging.getLogger(__name__)


@modal_handler(INCIDENT_CREATE_MODAL)
def create_incident(
    user_id: str, state: Any, metadata: str, trigger_id
):
    incident_name = state["name"]["name"]["value"]
    severity = state["severity"]["severity"]["selected_option"]["value"]
    summary = state["summary"]["summary"]["value"]
    lead_id = state["lead"]["lead"]["selected_user"]

    private = len(state["visibility"]["visibility"]["selected_options"]) > 0 and state["visibility"]["visibility"]["selected_options"][0]["value"] == "True"

    name = get_user_profile(user_id)["name"]
    reporter, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=name
    )

    lead = None
    if lead_id:
        lead_name = get_user_profile(lead_id)["name"]
        lead, _ = ExternalUser.objects.get_or_create_slack(
            external_id=lead_id, display_name=lead_name
        )

    incident = Incident.objects.create_incident(
        name=incident_name,
        reporter=reporter,
        incident_time=datetime.now(),
        summary=summary,
        lead=lead,
        severity=severity,
        updated_by=reporter,
        status_update_next=30,
        private=private
    )

    comms_channel = CommsChannel.objects.create_comms_channel(incident, private)

    modal = Modal(
        title=f"Incident created",
        blocks=[
            Section(
                text=f"Incident has been created 🚨\n\nInvite people into <#{comms_channel.channel_id}> to help manage this incident"
            )
        ]
    )

    try:
        modal.send_open_modal(INCIDENT_CREATED_MODAL, trigger_id=trigger_id)
    except SlackError as e:
        logger.error(f"Failed to send open modal for {incident_name}. Error: {e}")
    
    CommsChannel.objects.enrich_comms_channel(incident=incident,channel_id=comms_channel.channel_id)
    CommsChannel.objects.update_bookmarks_in_comms_channel(incident=incident,channel_id=comms_channel.channel_id)
    
    if(incident.private):
        _send_create_message(incident)
        return
    
    headline_post = HeadlinePost.objects.create_headline_post(incident=incident)
    headline_post.comms_channel = comms_channel
    headline_post.save()

    _send_create_message(incident)

@modal_handler(INCIDENT_EDIT_MODAL)
def edit_incident(
    user_id: str, state: Any, metadata: str, trigger_id
):
    incident_name = state["name"]["name"]["value"]
    severity = state["severity"]["severity"]["selected_option"]["value"]
    summary = state["summary"]["summary"]["value"]
    lead_id = state["lead"]["lead"]["selected_user"]

    updated_by = None
    if user_id:
        updated_by_name = get_user_profile(user_id)["name"]
        updated_by, _ = ExternalUser.objects.get_or_create_slack(
            external_id=user_id, display_name=updated_by_name
        )
    

    lead = None
    if lead_id:
        lead_name = get_user_profile(lead_id)["name"]
        lead, _ = ExternalUser.objects.get_or_create_slack(
            external_id=lead_id, display_name=lead_name
        )

    try:
        incident = Incident.objects.get(pk=metadata)

        if not severity and incident.severity:
            raise Exception("Cannot unset severity")

        # deliberately update in this way so the post_save signal gets sent
        # (required for the headline post to auto update)
        incident.name = incident_name
        incident.summary = summary
        incident.lead = lead
        incident.severity = severity
        incident.updated_by = updated_by
        incident.save()

    except Incident.DoesNotExist:
        logger.error(f"No incident found for pk {state}")

@modal_handler(UPDATE_SUMMARY_MODAL)
def update_summary(
    user_id: str, state: Any, metadata: str, trigger_id
):
    incident = Incident.objects.get(pk=metadata)
    summary = state["summary"]["summary"]["value"]

    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )  
    incident.updated_by = updated_by

    incident.summary = summary
    incident.save()

@modal_handler(SHARE_UPDATE_MODAL)
def share_update(
    user_id: str, state: Any, metadata: str, trigger_id
):
    incident = Incident.objects.get(pk=metadata)
    update = state["update"]["update"]["value"]

    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    ) 
    next_update = state["next_update"]["next_update"]["selected_option"]["value"]

    incident.updated_by = updated_by
    incident.status_update = update
    incident.status_update_last = datetime.utcnow()
    incident.status_update_next = next_update

    incident.save()


def _send_create_message(incident):
    from response.slack.block_kit import Header, Message, Section, Text, Actions
    msg = Message()

    msg.set_fallback_text(
        f"{incident.name} created by {user_reference(incident.reporter)}"
    )

    msg.add_block(
        Header(block_id="name", text=Text(f"{incident.status_emoji()} {incident.name} [{incident.severity_text().upper()}]", text_type="plain_text"))
    )
    if(incident.summary):
        msg.add_block(Section(text=Text(incident.summary))) 

    if not incident.is_closed():
        actions = Actions(block_id="actions")

        # Add all actions mapped by @headline_post_action decorators
        for key in sorted(SLACK_HEADLINE_POST_ACTION_MAPPINGS.keys()):
            funclist = SLACK_HEADLINE_POST_ACTION_MAPPINGS[key]
            for f in funclist:
                action = f(incident)
                if action:
                    actions.add_element(action)

        msg.add_block(actions)

    try:
        response = msg.send(incident.comms_channel().channel_id)
        msg.pin(incident.comms_channel().channel_id, response["ts"])
    except SlackError as e:
        logger.error(f"Failed to update channel message in {incident.comms_channel()}. Error: {e}")
import logging
from datetime import datetime
from typing import Any

from django.conf import settings

from response.core.models import ExternalUser, Incident
from response.slack.cache import get_user_profile
from response.slack.decorators import modal_handler
from response.slack.reference_utils import channel_reference
from response.slack.settings import INCIDENT_CREATE_MODAL, INCIDENT_EDIT_MODAL

logger = logging.getLogger(__name__)


@modal_handler(INCIDENT_CREATE_MODAL)
def report_incident(
    user_id: str, state: Any, channel_id: str
): 
    incident_name = state["name"]["name"]["value"]      
    severity = state["severity"]["severity"]["selected_option"]["value"]
    summary = state["summary"]["summary"]["value"]    
    lead_id = state["lead"]["lead"]["selected_user"]

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

    Incident.objects.create_incident(
        name=incident_name,
        reporter=reporter,        
        incident_time=datetime.now(),
        summary=summary,
        lead=lead,
        severity=severity,
    )

    incidents_channel_ref = channel_reference(settings.INCIDENT_CHANNEL_ID)

    text = (
        f"Thank you for raising the incident 🙏\n\nPlease head over to {incidents_channel_ref} "
        f"to help deal with the issue"
    )

    settings.SLACK_CLIENT.send_ephemeral_message(channel_id, user_id, text)


@modal_handler(INCIDENT_EDIT_MODAL)
def edit_incident(
    user_id: str, state: Any
):
    name = submission["report"]
    summary = submission["summary"]
    lead_id = submission["lead"]
    severity = submission["severity"]

    lead = None
    if lead_id:
        lead_name = get_user_profile(lead_id)["name"]
        lead, _ = ExternalUser.objects.get_or_create_slack(
            external_id=lead_id, display_name=lead_name
        )

    try:
        incident = Incident.objects.get(pk=state)

        if not severity and incident.severity:
            raise Exception("Cannot unset severity")

        # deliberately update in this way the post_save signal gets sent
        # (required for the headline post to auto update)
        incident.name = name
        incident.summary = summary
        incident.lead = lead
        incident.severity = severity
        incident.save()

    except Incident.DoesNotExist:
        logger.error(f"No incident found for pk {state}")

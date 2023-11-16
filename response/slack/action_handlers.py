import logging
from datetime import datetime

from response.core.models.incident import Incident
from response.slack.decorators import ActionContext, action_handler
from response.slack.modal_builder import (
    Modal,
    SelectFromUsers,
    SelectWithOptions,
    Text,
    TextArea,
)
from response.slack.models import CommsChannel, HeadlinePost
from response.slack.settings import INCIDENT_EDIT_MODAL

logger = logging.getLogger(__name__)


@action_handler(HeadlinePost.CLOSE_INCIDENT_BUTTON)
def handle_close_incident(ac: ActionContext):
    ac.incident.end_time = datetime.now()
    ac.incident.save()


@action_handler(HeadlinePost.CREATE_COMMS_CHANNEL_BUTTON)
def handle_create_comms_channel(ac: ActionContext):
    if CommsChannel.objects.filter(incident=ac.incident).exists():
        return

    comms_channel = CommsChannel.objects.create_comms_channel(ac.incident)

    # Update the headline post to link to this
    headline_post = HeadlinePost.objects.get(incident=ac.incident)
    headline_post.comms_channel = comms_channel
    headline_post.save()


@action_handler(HeadlinePost.EDIT_INCIDENT_BUTTON)
def handle_edit_incident_button(ac: ActionContext):
    modal_blocks = [
        Text(label="Name", name="name", value=ac.incident.name),
        TextArea(
            label="Summary",
            name="summary",
            value=ac.incident.summary,
            optional=True,
            multiline=True,
            placeholder="Can you share any more details?",
        ),
        SelectFromUsers(
            label="Lead",
            name="lead",
            value=ac.incident.lead.external_id if ac.incident.lead else None,
            optional=True,
        ),
        SelectWithOptions(
            [(s.capitalize(), i) for i, s in Incident.SEVERITIES],
            value=ac.incident.severity,
            label="Severity",
            name="severity",
            optional=True,
        ),
    ]

    print(ac.incident.pk)
    modal = Modal(
        title=f"Edit Incident {ac.incident.pk}",
        submit_label="Save",
        state=ac.incident.pk,
        blocks=modal_blocks,
    )
    modal.send_open_modal(INCIDENT_EDIT_MODAL, ac.trigger_id)

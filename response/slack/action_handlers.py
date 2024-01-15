import logging
from datetime import datetime
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse
from response.core.models.action import Action

from response.core.models.incident import Incident
from response.core.models.user_external import ExternalUser
from response.slack.cache import get_user_profile
from response.slack.decorators import ActionContext, action_handler
from response.slack.block_kit import Context, Message, Section
from response.slack.incident_notifications import ADD_SUMMARY_BUTTON, COMPLETE_ACTION_BUTTON, MAKE_ME_LEAD_BUTTON, SHARE_UPDATE_BUTTON, TAKE_ACTION_BUTTON
from response.slack.modal_builder import (
    Divider,
    Header,
    Modal,
    SelectFromUsers,
    SelectWithOptions,
    Text,
    TextArea,
)
from response.slack.models import HeadlinePost
from response.slack.reference_utils import user_reference
from response.slack.settings import INCIDENT_EDIT_MODAL, INCIDENT_OVERVIEW_MODAL, SHARE_UPDATE_MODAL, UPDATE_SUMMARY_MODAL

logger = logging.getLogger(__name__)


@action_handler(MAKE_ME_LEAD_BUTTON)
def handle_make_me_lead(ac: ActionContext):
    if(ac.incident.lead != None and ac.incident.lead.external_id == ac.user_id):
        return
    
    lead = None
    lead_name = get_user_profile(ac.user_id)["name"]
    lead, _ = ExternalUser.objects.get_or_create_slack(
        external_id=ac.user_id, display_name=lead_name
    )

    ac.incident.lead = lead
    ac.incident.updated_by = lead
    ac.incident.save()

@action_handler(TAKE_ACTION_BUTTON)
def handle_take_action(ac: ActionContext):
    action = Action.objects.get(pk=ac.value)

    assigned_to = None
    assigned_to_name = get_user_profile(ac.user_id)["name"]
    assigned_to, _ = ExternalUser.objects.get_or_create_slack(
        external_id=ac.user_id, display_name=assigned_to_name
    )

    action.assigned_to = assigned_to
    action.updated_by = assigned_to
    action.save()

@action_handler(COMPLETE_ACTION_BUTTON)
def handle_take_action(ac: ActionContext):
    action = Action.objects.get(pk=ac.value)

    completed_by = None
    completed_by_name = get_user_profile(ac.user_id)["name"]
    completed_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=ac.user_id, display_name=completed_by_name
    )

    if action.assigned_to == None:
        action.assigned_to = completed_by

    action.updated_by = completed_by
    action.done = True
    action.save()

@action_handler(ADD_SUMMARY_BUTTON)
def handle_add_summary(ac: ActionContext):
    modal = Modal(
        title="Update Summary",
        submit_label="Update",
        state=ac.incident.pk,
        blocks=[
            TextArea(
                label="Summary",
                name="summary",
                optional=False,
                multiline=True,
                placeholder="Enter a summary of the incident...",
                value=ac.incident.summary,
            )
        ],
    )

    modal.send_open_modal(UPDATE_SUMMARY_MODAL, ac.trigger_id)

@action_handler(SHARE_UPDATE_BUTTON)
def handle_share_update(ac: ActionContext):
    modal = Modal(
        title="Share Update",
        submit_label="Send",
        state=ac.incident.pk,
        blocks=[
            TextArea(
                label="Update",
                name="update",
                optional=False,
                multiline=True,
                placeholder="Share incident update..."
            )
        ],
    )

    modal.add_block(
        SelectWithOptions(
            [(s, i) for i, s in Incident.NEXT_STATUS_UPDATE],
            label="Next update in...",
            name="next_update",
            optional=False,
            placeholder="Next update in..."
        )
    )

    modal.send_open_modal(SHARE_UPDATE_MODAL, ac.trigger_id)

@action_handler(HeadlinePost.CLOSE_INCIDENT_BUTTON)
def handle_close_incident(ac: ActionContext):
    if(ac.incident.is_closed()):
        return
    
    updated_by_name = get_user_profile(ac.user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=ac.user_id, display_name=updated_by_name
    )    
    ac.incident.updated_by = updated_by

    ac.incident.end_time = datetime.now()
    ac.incident.save()

@action_handler(HeadlinePost.REQUEST_UPDATE_INCIDENT_BUTTON)
def handle_request_update(ac: ActionContext):
    if(ac.incident.is_closed()):
        return
    
    updated_by_name = get_user_profile(ac.user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=ac.user_id, display_name=updated_by_name
    )    

    msg = Message()
    msg.set_fallback_text("Incident request update")
    from response.slack.block_kit import Actions, Button, Text
    msg.add_block(
        Section(
            block_id="request update",
            text=Text(f"{user_reference(updated_by.external_id)} has requested a status update"),
        )
    )
    actions = Actions(block_id="actions")
    share_update = Button(":writing_hand: Share an update", SHARE_UPDATE_BUTTON, value=ac.incident.pk)
    actions.add_element(share_update)
    msg.add_block(actions)

    msg.send(ac.incident.comms_channel().channel_id)

@action_handler(HeadlinePost.EDIT_INCIDENT_BUTTON)
def handle_edit_incident_button(ac: ActionContext):
    modal = Modal(
        title=f"Edit Incident {ac.incident.pk}",
        submit_label="Save",
        state=ac.incident.pk,
        blocks=[
            Text(label="Name", name="name", value=ac.incident.name)
        ],
    )
    modal.add_block(
        SelectWithOptions(
            [(s.capitalize(), i) for i, s in Incident.SEVERITIES],
            value=ac.incident.severity,
            label="Severity",
            name="severity",
            optional=False,
        )
    )
    modal.add_block(
        TextArea(
            label="Summary",
            name="summary",
            value=ac.incident.summary,
            optional=True,
            multiline=True,
            placeholder="Can you share any more details?",
        )
    )
    modal.add_block(
        SelectFromUsers(
            label="Lead",
            name="lead",
            value=ac.incident.lead.external_id if ac.incident.lead else None,
            optional=True,
        )
    )

    modal.send_open_modal(INCIDENT_EDIT_MODAL, ac.trigger_id)

@action_handler(HeadlinePost.OVERVIEW_INCIDENT_BUTTON)
def handle_overview_incident_button(ac: ActionContext):
    open_overview_model(ac.incident, ac.trigger_id)


def open_overview_model(incident, trigger_id):

    modal = Modal(
        title="Incident overview",
        submit_label="",
        blocks=[Header(text=f"{incident.status_emoji()} {incident.name}")]
    )

    from response.slack.modal_builder import Section

    if(incident.summary):
        modal.add_block(Section(text=incident.summary))
        modal.add_block(Divider())

    modal.add_block(Section(text=f"{incident.severity_emoji()} *Severity*: `{incident.severity_text().upper()}`"))
    modal.add_block(Section(text=f":pager: *Status*: `{incident.status_text().upper()}`"))
    modal.add_block(Section(text=f":bust_in_silhouette: *Reporter*: {user_reference(incident.reporter.external_id)}"))

    if(incident.lead):
        incident_lead_text = (
            user_reference(incident.lead.external_id)
            if incident.lead
            else "-"
        )
        modal.add_block(Section(text=f":firefighter: *Incident Lead*: {incident_lead_text}"))

    actions = Action.objects.filter(incident=incident).order_by("created_date")
    if len(actions) > 0:
        modal.add_block(Divider())
        action_text = f"*Actions:*\n"
        for action in actions:
            assigned_to = f" :mechanic: {user_reference(action.assigned_to.external_id)}" if action.assigned_to else ""
            done = f"| :white_check_mark: " if action.done else ""
            action_text += f"`#{action.pk}` - {action.details} {assigned_to} {done}\n"
        modal.add_block(Section(text=action_text))

    modal.send_open_modal(INCIDENT_OVERVIEW_MODAL, trigger_id)

import logging
from datetime import datetime

from response.core.models import Action, ExternalUser, Incident
from response.slack.block_kit import Actions, Button, Message, Section, Text
from response.slack.cache import get_user_profile
from response.slack.client import SlackError
from response.slack.decorators import keyword_handler
from response.slack.decorators.incident_command import (
    __default_incident_command,
    get_help,
)
from response.slack.decorators.incident_notification import recurring_notification
from response.slack.incident_notifications import COMPLETE_ACTION_BUTTON, TAKE_ACTION_BUTTON
from response.slack.models import CommsChannel
from response.slack.reference_utils import reference_to_id, user_reference

logger = logging.getLogger(__name__)


@__default_incident_command(["help"], helptext="Display a list of commands and usage")
def send_help_text(incident: Incident, user_id: str, message: str, respond):
    return True, get_help()


@__default_incident_command(["lead"], helptext="Assign someone as the incident lead")
def set_incident_lead(incident: Incident, user_id: str, message: str, respond):
    assignee = reference_to_id(message) or user_id
    name = get_user_profile(assignee)["name"]
    user, _ = ExternalUser.objects.get_or_create_slack(
        external_id=assignee, display_name=name
    )

    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )
    incident.updated_by = updated_by
    incident.lead = user
    
    incident.save()
    return True, None


@__default_incident_command(["severity", "sev"], helptext="Set the incident severity")
def set_severity(incident: Incident, user_id: str, message: str, respond):
    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )    
    incident.updated_by = updated_by

    for sev_id, sev_name in Incident.SEVERITIES:
        # look for sev name (e.g. critical) or sev id (1)
        if (sev_name in message.lower()) or (sev_id in message.lower()):
            incident.severity = sev_id
            incident.save()
            return True, None

    return False, None


@__default_incident_command(["rename"], helptext="Rename the incident channel")
def rename_incident(incident: Incident, user_id: str, message: str, respond):
    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )
    incident.updated_by = updated_by

    try:
        comms_channel = CommsChannel.objects.get(incident=incident)
        logger.info(f"Renaming channel to {message}")
        comms_channel.rename(message)
    except SlackError:
        return (
            True,
            "👋 Sorry, the channel couldn't be renamed. Make sure that name isn't taken already and it's not too long.",
        )
    return True, None


@__default_incident_command(
    ["duration"], helptext="Returns how long has this incident been running"
)
def get_duration(incident: Incident, user_id: str, message: str, respond):
    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )
    incident.updated_by = updated_by

    duration = incident.duration()
    text = f"The incident has been running for {duration}"
    if respond != None:
        respond(text)
    else:
        comms_channel = CommsChannel.objects.get(incident=incident)
        comms_channel.post_in_channel(text)

    return True, None


@__default_incident_command(["close"], helptext="Close this incident")
def close_incident(incident: Incident, user_id: str, message: str, respond):
    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )
    incident.updated_by = updated_by

    comms_channel = CommsChannel.objects.get(incident=incident)

    if incident.is_closed():
        comms_channel.post_in_channel(
            f"This incident was already closed at {incident.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return True, None

    incident.end_time = datetime.now()
    incident.save()

    #comms_channel.post_in_channel("This incident has been closed! 📖 ⟶ 📕")
    
    return True, None


@__default_incident_command(
    ["actions"], helptext="Returns actions"
)
def get_actions(incident: Incident, user_id: str, message: str, respond):
    open_actions = Action.objects.filter(incident=incident, done=False)
    completed_actions = Action.objects.filter(incident=incident, done=True)

    text = ""
    if len(open_actions) > 0:    
        text += f"Open actions:\n"
        for action in open_actions:
            assigned_to = f" :mechanic: {user_reference(action.assigned_to.external_id)}" if action.assigned_to else ""
            text += f"`#{action.pk}` - {action.details} {assigned_to}\n"

    if len(completed_actions) > 0:    
        text += f"\nCompleted actions:\n"
        for action in completed_actions:
            assigned_to = f" :mechanic: {user_reference(action.assigned_to.external_id)}" if action.assigned_to else ""
            text += f"`#{action.pk}` - {action.details} {assigned_to}\n"
    
    if text == "":
        text = "There are no actions for this incident"
    
    if respond != None:
        respond(text)
    else:
        comms_channel = CommsChannel.objects.get(incident=incident)
        comms_channel.post_in_channel(text)

    return True, None


@__default_incident_command(["action"], helptext="Log a follow up action")
def set_action(incident: Incident, user_id: str, message: str, respond):
    if message == "":
        return False, "No action specified"
    
    updated_by_name = get_user_profile(user_id)["name"]
    updated_by, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=updated_by_name
    )
    incident.updated_by = updated_by

    name = get_user_profile(user_id)["name"]
    action_reporter, _ = ExternalUser.objects.get_or_create_slack(
        external_id=user_id, display_name=name
    )
    action = Action(incident=incident, details=message, created_by=action_reporter)
    action.updated_by = action_reporter
    action.save()

    comms_channel = CommsChannel.objects.get(incident=incident)
    msg = Message()

    msg.set_fallback_text("Action created")
    msg.add_block(Section(text=Text(f":memo: Action created #{action.pk}:\n>>>{action.details}")))
    actions = Actions(block_id="actions")
    take_action = Button(":hand: I can take this", TAKE_ACTION_BUTTON, value=action.pk)
    complete_action = Button(":white_check_mark: Complete", COMPLETE_ACTION_BUTTON, value=action.pk)
    actions.add_element(take_action)
    actions.add_element(complete_action)
    msg.add_block(actions)

    msg.send(comms_channel.channel_id)

    return True, None

# TODO: decide if needed
#@keyword_handler(['runbook', 'run book'])
#def runbook_notification(comms_channel: CommsChannel, user: str, keyword: str, text: str, ts: str):
#    comms_channel.post_in_channel("📗 If you're looking for our runbooks they can be found here https://...")

import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from response.core.models.incident import Incident
from response.slack.authentication import slack_authenticate
from response.slack.cache import update_user_cache
from response.slack.decorators import (
    handle_action,
    handle_modal,
    handle_event,
    handle_notifications,
)
from response.slack.modal_builder import (
    Modal,
    SelectFromUsers,
    SelectWithOptions,
    Text,
    TextArea,
)
from response.slack.settings import INCIDENT_CREATE_MODAL

logger = logging.getLogger(__name__)


@csrf_exempt
@slack_authenticate
def slash_command(request):
    """
    Handles slash commands from slack
    More details here: https://api.slack.com/slash-commands
    Note: The order the elements are specified is the order they
    appear in the slack modal

    @param request the request from slack containing the slash command
    @return: return a HTTP response to indicate the request was handled
    """

    user_id = request.POST.get("user_id")
    trigger_id = request.POST.get("trigger_id")
    report = request.POST.get("text")

    modal = Modal(
        title="Report an Incident",
        submit_label="Report",
        blocks=[
            Text(
                label="Title",
                name="report",
                placeholder="What's happened, in a sentence?",
                value=report,
            )
        ],
    )

    modal.add_block(
        TextArea(
            label="Summary",
            name="summary",
            optional=True,
            placeholder="Can you share any more details?",
        )
    )

    modal.add_block(SelectFromUsers(label="Lead", name="lead", optional=True))

    modal.add_block(
        SelectWithOptions(
            [(s.capitalize(), i) for i, s in Incident.SEVERITIES],
            label="Severity",
            name="severity",
            optional=True,
        )
    )

    logger.info(
        f"Handling Slack slash command for user {user_id}, report {report} - opening modal"
    )

    modal.send_open_modal(INCIDENT_CREATE_MODAL, trigger_id)
    return HttpResponse()


@csrf_exempt
@slack_authenticate
def action(request):
    """
    Handles actions sent from Slack.

    @param request the request from slack containing an action
    @return: return a HTTP response to indicate the request was handled
    """
    payload = json.loads(request.POST["payload"])
    action_type = payload["type"]

    logger.info(f"Handling Slack action of type '{action_type}'")

    if action_type == "dialog_submission":
        handle_modal.after_response(payload)
    elif action_type == "block_actions":
        handle_action.after_response(payload)
    else:
        logger.error(f"No handler for action type {action_type}")

    return HttpResponse()


@csrf_exempt
@slack_authenticate
def event(request):
    """
    Handles events sent from Slack.

    Details: We can configure our Slack app receive specific events, and doing so tells
    slack to call this endpoint with a JSON payload representing the event.

    See here for reference: https://api.slack.com/events-api

    @param request the request from slack containing an event
    @return: return a HTTP response to indicate the request was handled
    """
    payload = json.loads(request.body)
    action_type = payload["type"]

    logger.info(f"Handling Slack event of type '{action_type}'")

    if action_type == "event_callback":
        handle_event(payload)
    elif action_type == "url_verification":
        # the url_verification event is called when we change the registered event callback url
        # in the Sl ack app configuration.  It expects us to return the challenge token sent in
        # the request
        return HttpResponse(payload["challenge"])

    return HttpResponse()


@csrf_exempt
def cron_minute(request):
    "Handles actions that need to take place every minute"
    handle_notifications()
    return HttpResponse()


@csrf_exempt
def cron_daily(request):
    "Handles actions that need to take place every day"
    update_user_cache()
    return HttpResponse()


import logging
import re

from slack_bolt import App
from response.slack.action_handlers import open_overview_model
from response.slack.decorators.incident_command import handle_incident_command
from response.slack.event_handlers import  decode_command
from response.slack.models import CommsChannel
from response.core.models.incident import Incident
from response.slack.modal_builder import (
    Checkboxes,
    Modal,
    SelectFromUsers,
    SelectWithOptions,
    Text,
    TextArea,
)
from response.slack.settings import INCIDENT_CREATE_MODAL

logger = logging.getLogger(__name__)

def command_listeners(app: App):
    @app.command("/incident")
    def incident(ack, body, channel_id, respond):
        ack()
       
        try:
            # check if the command is being run from an existing incident channel
            comms_channel = CommsChannel.objects.get(channel_id=channel_id)
            incident = comms_channel.incident
            _handle_existing_incident_command(incident, body, channel_id, respond)
        except CommsChannel.DoesNotExist:
            _handle_new_command(body, channel_id)
    
    def _handle_existing_incident_command(incident, body, channel_id, respond):
        # could replace with proper command line parsing
        if(body["text"] == ""):
            _handle_incident_overview(incident, body)

        command_name, message = decode_command(body["text"])

        user_id = body["user_id"]
        handle_incident_command(command_name, message, None, channel_id, user_id, respond)

    def _handle_new_command(body, channel_id):
        user_id = body["user_id"]
        trigger_id = body["trigger_id"]
        input = body["text"]
        logger.info(f"Handling Slack slash command for user {user_id}, incident name {input} - opening modal")

        modal = Modal(
            title="Create Incident",
            submit_label="Create",
            blocks=[
                Text(
                    label="Incident Name",
                    name="name",
                    placeholder="Incident Name",
                    value=input,
                    optional=False,
                    hint="The name of the incident will be used to create a slack channel"
                )
            ]
        )

        modal.add_block(
            SelectWithOptions(
                [(s.capitalize(), i) for i, s in Incident.SEVERITIES],
                label="Severity",
                name="severity",                
                optional=False,
                placeholder="Select Severity"
            )
        )

        modal.add_block(
            TextArea(
                label="Summary",
                name="summary",
                optional=True,
                multiline=True,
                placeholder="Can you share any useful details?",
                hint="Your current understanding of what is happening and the impact it is having. Fine to go into detail here."
            )
        )

        modal.add_block(SelectFromUsers(label="Lead", name="lead", optional=True, placeholder="Select who is leading the issue"))

        modal.add_block(Checkboxes([("Make this a private incident (default is public)", "True")], label="Visibility", name="visibility", optional=True))

        logger.info(
            f"Handling Slack slash command for user {user_id}, incident name {input} - opening modal"
        )

        modal.send_open_modal(INCIDENT_CREATE_MODAL, trigger_id)

    def _handle_incident_overview(incident, body):
        trigger_id = body["trigger_id"]
        open_overview_model(incident, trigger_id)

    @app.view({"type": "view_submission", "callback_id": re.compile(".*")})
    def modal_submission(ack, body, logger, say, respond):
        ack()
        action_type = body["view"]["callback_id"]
        logger.info(f"Handling Slack action of type {action_type}")

        from response.slack.decorators.modal_handler import handle_modal
        handle_modal(body, action_type)

    @app.action({"type": "block_actions", "action_id": re.compile(".*")})
    def block_actions(ack, body, logger):
        ack()
        logger.info(f"Handling Slack block action")

        from response.slack.decorators.action_handler import handle_action
        handle_action(body)

    @app.event(re.compile(".*"))
    def handle_events(body, logger):
        action_type = body["type"]

        logger.info(f"Handling Slack event of type '{action_type}'")

        if action_type == "event_callback":
            from response.slack.decorators.event_handler import handle_event
            handle_event(body)


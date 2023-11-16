
import logging
import re

from slack_bolt import App

logger = logging.getLogger(__name__)

def command_listeners(app: App):
    @app.command("/incident")
    def incident(ack, body, logger, channel_id):
        ack()
        user_id = body["user_id"]
        trigger_id = body["trigger_id"]
        input = body["text"]

        from response.core.models.incident import Incident

        from response.slack.modal_builder import (
            Modal,
            SelectFromUsers,
            SelectWithOptions,
            Text,
            TextArea,
        )
        from response.slack.settings import INCIDENT_CREATE_MODAL

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
            ],
            state=channel_id
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

        modal.add_block(SelectFromUsers(label="Lead", name="lead", optional=True, placeholder="Select lead"))

        logger.info(
            f"Handling Slack slash command for user {user_id}, incident name {input} - opening modal"
        )

        modal.send_open_modal(INCIDENT_CREATE_MODAL, trigger_id)

    @app.view({"type": "view_submission", "callback_id": re.compile(".*")})
    def modal_submission(ack, body, logger):
        ack()
        action_type = body["view"]["callback_id"]
        channel_id = body["view"]["private_metadata"]
        logger.info(f"Handling Slack action of type {action_type}")

        from response.slack.decorators.modal_handler import handle_modal
        handle_modal(body, action_type, channel_id)

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


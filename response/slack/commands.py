
import logging
import re

from slack_bolt import App

logger = logging.getLogger(__name__)

def command_listeners(app: App):
    @app.command("/incident")
    def incident(ack, body, logger):
        ack()
        user_id = body["user_id"]
        trigger_id = body["trigger_id"]
        report = body["text"]

        from response.core.models.incident import Incident

        from response.slack.dialog_builder import (
            Dialog,
            SelectFromUsers,
            SelectWithOptions,
            Text,
            TextArea,
        )
        from response.slack.settings import INCIDENT_REPORT_DIALOG
        dialog = Dialog(
            title="Report an Incident",
            submit_label="Report",
            elements=[
                Text(
                    label="Title",
                    name="report",
                    placeholder="What's happened, in a sentence?",
                    value=report,
                )
            ],
        )

        dialog.add_element(
            SelectWithOptions(
                [
                    ("Yes - this is a live incident happening right now", "live"),
                    ("No - this is just a report of something that happened", "report"),
                ],
                label="Is this a live incident?",
                name="incident_type",
                optional=False,
            )
        )

        dialog.add_element(
            TextArea(
                label="Summary",
                name="summary",
                optional=True,
                placeholder="Can you share any more details?",
            )
        )

        dialog.add_element(
            TextArea(
                label="Impact",
                name="impact",
                optional=True,
                placeholder="Who or what might be affected?",
                hint="Think about affected people, systems, and processes",
            )
        )

        dialog.add_element(SelectFromUsers(label="Lead", name="lead", optional=True))

        dialog.add_element(
            SelectWithOptions(
                [(s.capitalize(), i) for i, s in Incident.SEVERITIES],
                label="Severity",
                name="severity",
                optional=True,
            )
        )

        logger.info(
            f"Handling Slack slash command for user {user_id}, report {report} - opening dialog"
        )

        dialog.send_open_dialog(INCIDENT_REPORT_DIALOG, trigger_id)

    @app.action({"type": "dialog_submission", "callback_id": re.compile(".*")})
    def dialog_submission(ack, body, logger):
        ack()
        action_type = body["callback_id"]
        logger.info(f"Handling Slack action of type {action_type}")

        from response.slack.decorators.dialog_handler import handle_dialog
        handle_dialog(body)

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


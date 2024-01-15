from datetime import datetime, timedelta

from response.core.models import Incident
from response.slack.block_kit import Actions, Button, Message, Section, Text
from response.slack.decorators import recurring_notification
from response.slack.decorators.incident_notification import single_notification
from response.slack.models import CommsChannel
from response.slack.reference_utils import user_reference

MAKE_ME_LEAD_BUTTON = "make-me-lead-button"
TAKE_ACTION_BUTTON = "take-action-button"
COMPLETE_ACTION_BUTTON = "complete-action-button"
ADD_SUMMARY_BUTTON = "add-summary-button"
SHARE_UPDATE_BUTTON = "share-update-button"

@recurring_notification(interval_mins=10, max_notifications=5)
@single_notification()
def remind_incident_lead(incident: Incident):
    try:
        comms_channel = CommsChannel.objects.get(incident=incident)
        if not incident.lead:
            msg = Message()

            msg.set_fallback_text("Inident doesn't have a lead")
            msg.add_block(Section(text=Text(":firefighter: This incident doesn't have a lead")))
            actions = Actions(block_id="actions")
            set_lead = Button(":hand: Make me lead", MAKE_ME_LEAD_BUTTON, value=incident.pk)
            actions.add_element(set_lead)
            msg.add_block(actions)

            msg.send(comms_channel.channel_id)
    except CommsChannel.DoesNotExist:
        pass

@recurring_notification(interval_mins=10, max_notifications=5)
@single_notification()
def remind_incident_summary(incident: Incident):
    try:
        comms_channel = CommsChannel.objects.get(incident=incident)
        if not incident.summary:
            msg = Message()

            msg.set_fallback_text("Inident doesn't have a summary")
            msg.add_block(Section(text=Text("No summary has been set yet")))
            actions = Actions(block_id="actions")
            add_summary = Button(":pencil: Add a summary", ADD_SUMMARY_BUTTON, value=incident.pk)
            actions.add_element(add_summary)
            msg.add_block(actions)

            msg.send(comms_channel.channel_id)
    except CommsChannel.DoesNotExist:
        pass

@recurring_notification(interval_mins=60*24, max_notifications=2)
def remind_close_incident(incident: Incident):

    # Only remind on weekdays (weekday returns an ordinal indexed from 0 on Monday)
    if datetime.now().weekday() in (5, 6):
        return

    # Only remind during the day to prevent alerting people at unsociable hours
    if datetime.now().hour not in range(8, 18):
        return

    try:
        comms_channel = CommsChannel.objects.get(incident=incident)
        if not incident.is_closed():
            user_to_notify = incident.lead or incident.reporter
            comms_channel.post_in_channel(
                f":timer_clock: {user_reference(user_to_notify.external_id)}> - this incident has been running a long time,"
                "can it be closed now?"
            )
    except CommsChannel.DoesNotExist:
        pass

@recurring_notification(interval_mins=1, max_notifications=None)
def remind_share_update(incident: Incident):
    try:
        comms_channel = CommsChannel.objects.get(incident=incident)
        if incident.is_closed() or incident.status_update_next is None:
            return
        else:
            next_time = (incident.status_update_last or incident.start_time) + timedelta(minutes=int(incident.status_update_next))
            if datetime.utcnow() <= next_time:
                return
            
        user_to_notify = incident.lead or incident.reporter

        msg = Message()
        msg.set_fallback_text("Incident update is due")
        msg.add_block(Section(text=Text(f":mega: {user_reference(user_to_notify.external_id)} - an update is due for this incident")))
        actions = Actions(block_id="actions")
        share_update = Button(":writing_hand: Share an update", SHARE_UPDATE_BUTTON, value=incident.pk)
        actions.add_element(share_update)
        msg.add_block(actions)

        msg.send(comms_channel.channel_id)
        incident.status_update_next = None
        incident.save()
    except CommsChannel.DoesNotExist:
        pass
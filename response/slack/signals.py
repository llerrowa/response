from urllib.parse import urljoin

from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from response.core.models import Incident, add_incident_update_event
from response.core.models.action import Action
from response.core.serializers import ExternalUserSerializer
from response.slack.models import HeadlinePost
from response.slack.block_kit import Context, Message, Section, Text
from response.slack.models.comms_channel import CommsChannel
from response.slack.reference_utils import user_reference

@receiver(post_save, sender=Incident)
def update_headline_after_incident_save(sender, instance, **kwargs):
    """
    Reflect changes to incidents in the headline post

    Important: this is called in the synchronous /incident flow so must remain fast (<2 secs)

    """
    try:
        comms_channel = instance.comms_channel()
        if comms_channel != None:
            CommsChannel.objects.update_bookmarks_in_comms_channel(incident=instance,channel_id=comms_channel.channel_id)
        
        if instance.private:
            return
        
        headline_post = HeadlinePost.objects.get(incident=instance)
        headline_post.update_main_in_slack()

    except HeadlinePost.DoesNotExist:
        # will be created shortly
        return


@receiver(pre_save, sender=Incident)
def prompt_incident_report(sender, instance: Incident, **kwargs):
    """
    Prompt incident lead to complete a report when an incident is closed.
    """

    try:
        prev_state = Incident.objects.get(pk=instance.pk)
    except Incident.DoesNotExist:
        # Incident hasn't been saved yet, nothing to do here.
        return

    if instance.is_closed() and not prev_state.is_closed():
        user_to_notify = instance.lead or instance.reporter
        doc_url = urljoin(
            settings.SITE_URL,
            reverse("incident_doc", kwargs={"incident_id": instance.pk}),
        )
        settings.SLACK_CLIENT.send_message(
            user_to_notify.external_id,
            f"👋 Don't forget to fill out an incident report, the timeline from: {doc_url} may be helpful.",
        )


@receiver(post_save, sender=HeadlinePost)
def update_headline_after_save(sender, instance, **kwargs):
    """
    Reflect changes to headline posts in slack

    """
    instance.update_main_in_slack()

@receiver(pre_save, sender=Action)
def add_timeline_events(sender, instance, **kwargs):
    try:
        prev_state = Action.objects.get(pk=instance.pk)
    except Action.DoesNotExist:
        # New action
        text = f"Action created: {instance.details}"
        add_incident_update_event(
            incident=instance.incident,
            update_type="action_created",
            text=text,
            old_value=None,
            new_value=text,
        )
        return
    
    msg = ""
    if prev_state.assigned_to != instance.assigned_to:
        old_assigned = None
        if prev_state.assigned_to:
            old_assigned = ExternalUserSerializer(prev_state.assigned_to).data

        new_assigned = None
        if instance.assigned_to:
            new_assigned = ExternalUserSerializer(instance.assigned_to).data

        text = f":firefighter: {user_reference(instance.assigned_to.display_name)} has been assigned to action #{instance.pk} - {instance.details}"
        add_incident_update_event(
            incident=instance.incident,
            update_type="action_assigned",
            text=text,
            old_value=old_assigned,
            new_value=new_assigned,
        )
        text += "\n"
        msg += text
    
    if prev_state.done != instance.done:
        text = f":white_check_mark: {user_reference(instance.assigned_to.display_name)} has completed action #{instance.pk} - {instance.details}"
        add_incident_update_event(
            incident=instance.incident,
            update_type="action_complete",
            text=text,
            old_value=prev_state.done,
            new_value=instance.done,
        )
        text += "\n"
        msg += text

    if msg != "":
        _notify_message_text(instance, msg)

@receiver(pre_save, sender=Incident)
def add_timeline_events(sender, instance: Incident, **kwargs):
    try:
        prev_state = Incident.objects.get(pk=instance.pk)
    except Incident.DoesNotExist:
        # Incident hasn't been saved yet, nothing to do here.
        return

    text = ""
    if prev_state.lead != instance.lead:
        text = update_incident_lead_event(prev_state, instance)
        _notify_message_text(instance, text)

    if prev_state.name != instance.name:
        text = update_incident_name_event(prev_state, instance)
        _notify_message_text(instance, text)

    if prev_state.summary != instance.summary:
        text = update_incident_summary_event(prev_state, instance)
        _notify_message_text(instance, text)

    if prev_state.severity != instance.severity:
        text = update_incident_severity_event(prev_state, instance)
        _notify_message_text(instance, text)

    if prev_state.status_update_last != instance.status_update_last:
        text = share_incident_update_event(prev_state, instance)
        _notify_message_text(instance, text, instance.status_update_text())

    if prev_state.is_closed() != instance.is_closed():
        msg = share_incident_closed_event(prev_state, instance)
        _notify(instance, msg)
        doc_url = urljoin(
                settings.SITE_URL,
                reverse("incident_doc", kwargs={"incident_id": instance.pk}),
            )
        settings.SLACK_CLIENT.send_message(
            instance.comms_channel().channel_id,
            f"👋 Don't forget to fill out an incident report, the timeline from: {doc_url} may be helpful.",
            )

def _notify(instance, msg):
    if type(instance) == Action:
        channel_id = instance.incident.comms_channel().channel_id
        incident = instance.incident
    else:
        channel_id = instance.comms_channel().channel_id
        incident = instance

    msg.send(channel_id)

    if incident.private:
        return
    
    headline_post = HeadlinePost.objects.get(incident=incident)
    headline_post.post_to_thread(msg)


def _notify_message_text(instance, msg_text, next_update = None):
    msg = Message()
    msg.set_fallback_text(msg_text)
    msg.add_block(
        Section(
            block_id="update",
            text=Text(msg_text),
        )
    )
    
    context_text = None
    if(instance.updated_by != None):
        context_text = f"Updated by {user_reference(instance.updated_by.display_name)}"
    if(next_update != None):
        context_text += f", next update due in {next_update}"    
    if(context_text != None):
        context = Context(block_id="update_context")
        context.add_element(Text(context_text))
        msg.add_block(context)

    _notify(instance, msg)

def update_incident_lead_event(prev_state, instance):
    old_lead = None
    if prev_state.lead:
        old_lead = ExternalUserSerializer(prev_state.lead).data

    new_lead = None
    if instance.lead:
        new_lead = ExternalUserSerializer(instance.lead).data

    if prev_state.lead:
        if instance.lead:
            text = f":firefighter: Incident lead changed from {user_reference(prev_state.lead.external_id)} to {user_reference(instance.lead.external_id)}"
            event_text = f":firefighter: Incident lead changed from {prev_state.lead.display_name} to {instance.lead.display_name}"
        else:
            text = f":firefighter: {user_reference(prev_state.lead.external_id)} was removed as incident lead"
            event_text = f":firefighter: {instance.lead.display_name} was removed as incident lead"

    else:
        text = f":firefighter: {user_reference(instance.lead.external_id)} was added as incident lead"
        event_text = f":firefighter: {instance.lead.display_name} was added as incident lead"

    add_incident_update_event(
        incident=instance,
        update_type="incident_lead",
        text=event_text,
        old_value=old_lead,
        new_value=new_lead,
    )

    return text


def update_incident_name_event(prev_state, instance):
    text = f':ledger: Incident name updated from "{prev_state.name}" to "{instance.name}"'
    add_incident_update_event(
        incident=instance,
        update_type="incident_name",
        text=text,
        old_value=prev_state.name,
        new_value=instance.name,
    )

    return text


def update_incident_summary_event(prev_state, instance):
    if prev_state.summary:
        text = f':writing_hand: Incident summary updated from {prev_state.summary} to {instance.summary}'
    else:
        text = f':writing_hand: Incident summary added: {instance.summary}'

    add_incident_update_event(
        incident=instance,
        update_type="incident_summary",
        text=text,
        old_value=prev_state.summary,
        new_value=instance.summary,
    )

    return text


def update_incident_severity_event(prev_state, instance):
    if prev_state.severity:
        text = f"{instance.severity_emoji()} Incident severity updated from `{prev_state.severity_text().upper()}` to `{instance.severity_text().upper()}`"
    else:
        text = f"{instance.severity_emoji()} Incident severity set to `{instance.severity_text().upper()}`"

    add_incident_update_event(
        incident=instance,
        update_type="incident_severity",
        text=text,
        old_value={
            "id": prev_state.severity,
            "text": prev_state.severity_text().upper() if prev_state else "",
        },
        new_value={"id": instance.severity, "text": instance.severity_text().upper()},
    )

    return text

def share_incident_update_event(prev_state, instance):
    text = f":mega: Incident update shared:\n"
    text += f">>>{instance.status_update}\n"

    add_incident_update_event(
        incident=instance,
        update_type="incident_status_update",
        text=text,
        old_value=None,
        new_value=instance.status_update,
    )

    return text   

def share_incident_closed_event(prev_state, instance):
    msg = Message()
    text = "✅ *Incident closed*"
    msg.set_fallback_text("Incident closed")
    from response.slack.block_kit import Text
    msg.add_block(
        Section(
            block_id="update",
            text=Text(text),
        )
    )
    
    if(instance.updated_by != None):
        context = Context(block_id="update_context")
        context.add_element(Text(f"Updated by {user_reference(instance.updated_by.display_name)}"))
        msg.add_block(
            context
        )

    add_incident_update_event(
        incident=instance,
        update_type="incident_closed",
        text=text,
        old_value=None,
        new_value=instance.is_closed(),
    )

    return msg 
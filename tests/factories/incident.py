import random

import factory.django
from django.db.models.signals import post_save
from faker import Factory

from response.core.models import Incident
from response.slack.models import CommsChannel

from .action import ActionFactory

faker = Factory.create()


class CommsChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CommsChannel


@factory.django.mute_signals(post_save)
class IncidentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Incident

    name = factory.LazyFunction(
        lambda: faker.paragraph(nb_sentences=3, variable_nb_sentences=True)
    )
    incident_time = factory.LazyFunction(
        lambda: faker.date_time_between(start_date="-6m", end_date="now", tzinfo=None)
    )

    reporter = factory.SubFactory("tests.factories.ExternalUserFactory")
    lead = factory.SubFactory("tests.factories.ExternalUserFactory")

    start_time = factory.LazyFunction(
        lambda: faker.date_time_between(start_date="-6m", end_date="now", tzinfo=None)
    )

    if random.random() > 0.5:
        end_time = factory.LazyAttribute(
            lambda a: faker.date_time_between(start_date=a.start_time, end_date="now")
        )

    severity = factory.LazyFunction(lambda: str(random.randint(1, 4)))
    summary = factory.LazyFunction(
        lambda: faker.paragraph(nb_sentences=3, variable_nb_sentences=True)
    )

    related_channel = factory.RelatedFactory(CommsChannelFactory, "incident")
    related_action_items = factory.RelatedFactoryList(
        ActionFactory, "incident", size=lambda: random.randint(1, 5)
    )
    related_timeline_events = factory.RelatedFactoryList(
        "tests.factories.TimelineEventFactory",
        "incident",
        size=lambda: random.randint(1, 20),
    )

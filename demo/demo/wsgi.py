"""
WSGI config for demo project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from response.slack.commands import command_listeners
from slack_bolt.adapter.socket_mode import SocketModeHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings.dev")

application = get_wsgi_application()

from slack_bolt import App

app = App(token=settings.SLACK_TOKEN)
command_listeners(app)

handler = SocketModeHandler(app, settings.SLACK_APP_TOKEN)
handler.connect()

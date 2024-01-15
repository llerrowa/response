from django.conf import settings

INCIDENT_CREATE_MODAL = "incident-create-modal"
INCIDENT_CREATED_MODAL = "incident-created-modal"
INCIDENT_EDIT_MODAL = "incident-edit-modal"
INCIDENT_OVERVIEW_MODAL = "incident-overview-modal"
UPDATE_SUMMARY_MODAL = "update-summary-modal"
SHARE_UPDATE_MODAL = "share-update-modal"

SLACK_API_MOCK = getattr(settings, "SLACK_API_MOCK", None)

if SLACK_API_MOCK:
    from urllib.parse import urlparse
    from slack_sdk.slackrequest import requests

    old_post = requests.post

    import logging

    def fake_post(url, *args, **kwargs):
        parsed = urlparse(url)
        newurl = parsed._replace(netloc=SLACK_API_MOCK, scheme="http")
        logging.info(f"Fake Slack client request: HTTP POST {SLACK_API_MOCK} {newurl}")
        return old_post(newurl.geturl(), *args, **kwargs)

    requests.post = fake_post

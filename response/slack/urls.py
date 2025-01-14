from django.urls import path

from response.slack import views

urlpatterns = [
    path("action", views.action, name="action"),
    path("event", views.event, name="event"),
    path("cron_minute", views.cron_minute, name="cron_minute"),
    path("cron_daily", views.cron_daily, name="cron_daily"),
]

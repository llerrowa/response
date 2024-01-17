# Generated by Django 4.2.7 on 2024-01-02 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('response', '0021_remove_incident_status_update_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='incident',
            name='status_update_next',
            field=models.CharField(blank=True, choices=[('5', '5 mins'), ('10', '10 mins'), ('30', '30 mins'), ('60', '1 hour')], max_length=10, null=True),
        ),
    ]
# Generated by Django 4.2.7 on 2024-01-13 10:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('response', '0023_remove_action_done_date_remove_action_due_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='user',
        ),
    ]

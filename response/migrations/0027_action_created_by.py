# Generated by Django 4.2.7 on 2024-01-13 11:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('response', '0026_alter_action_assigned_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_by', to='response.externaluser'),
        ),
    ]

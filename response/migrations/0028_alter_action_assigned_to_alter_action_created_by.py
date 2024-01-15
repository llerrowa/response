# Generated by Django 4.2.7 on 2024-01-13 11:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('response', '0027_action_created_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='assigned_to',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assigned_to', to='response.externaluser'),
        ),
        migrations.AlterField(
            model_name='action',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='created_by', to='response.externaluser'),
        ),
    ]

# Generated by Django 5.1.5 on 2025-02-12 03:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_appmessage_is_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='pitchdeck',
            name='ai_analysis_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pitchdeck',
            name='ai_analysis_status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('DISABLED', 'Disabled')], default='DISABLED', max_length=20),
        ),
    ]

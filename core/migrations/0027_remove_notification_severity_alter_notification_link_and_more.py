# Generated by Django 5.1.4 on 2025-02-15 23:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_pitchdeck_ai_analysis_error_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notification',
            name='severity',
        ),
        migrations.AlterField(
            model_name='notification',
            name='link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[('INVESTMENT', 'Investment'), ('PRICE', 'Price Alert'), ('APP_APPROVAL', 'App Approval'), ('SYSTEM', 'System'), ('MILESTONE', 'Milestone'), ('APP_UPDATE', 'App Update'), ('FUNDING_GOAL', 'Funding Goal'), ('DIVIDEND', 'Dividend'), ('SECURITY', 'Security'), ('MAINTENANCE', 'Maintenance'), ('NEWS', 'News')], max_length=20),
        ),
        migrations.AlterField(
            model_name='notificationtemplate',
            name='type',
            field=models.CharField(choices=[('INVESTMENT', 'Investment'), ('PRICE', 'Price Alert'), ('APP_APPROVAL', 'App Approval'), ('SYSTEM', 'System'), ('MILESTONE', 'Milestone'), ('APP_UPDATE', 'App Update'), ('FUNDING_GOAL', 'Funding Goal'), ('DIVIDEND', 'Dividend'), ('SECURITY', 'Security'), ('MAINTENANCE', 'Maintenance'), ('NEWS', 'News')], max_length=20),
        ),
    ]

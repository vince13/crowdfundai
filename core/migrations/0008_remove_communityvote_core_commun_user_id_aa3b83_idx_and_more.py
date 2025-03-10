# Generated by Django 5.1.5 on 2025-01-29 22:22

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_releaserequest'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='communityvote',
            name='core_commun_user_id_aa3b83_idx',
        ),
        migrations.AlterUniqueTogether(
            name='communityvote',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='notification',
            name='severity',
            field=models.CharField(choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')], default='LOW', max_length=10),
        ),
        migrations.AlterField(
            model_name='communityvote',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='communityvote',
            name='vote_type',
            field=models.CharField(choices=[('LIKE', 'Like'), ('UPVOTE', 'Upvote')], max_length=10),
        ),
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[('INVESTMENT', 'Investment Update'), ('PRICE', 'Price Alert'), ('SYSTEM', 'System Notification'), ('SYSTEM_ERROR', 'System Error'), ('MILESTONE', 'Portfolio Milestone'), ('APP_UPDATE', 'App Update'), ('FUNDING_GOAL', 'Funding Goal Reached'), ('DIVIDEND', 'Dividend Payment'), ('SECURITY', 'Security Alert'), ('MAINTENANCE', 'System Maintenance'), ('NEWS', 'App News'), ('APP_APPROVAL', 'App Approval Status'), ('PAYMENT_PENDING', 'Payment Processing'), ('FUNDING_COMPLETE', 'Funding Complete')], max_length=20),
        ),
        migrations.AlterField(
            model_name='notificationtemplate',
            name='type',
            field=models.CharField(choices=[('INVESTMENT', 'Investment Update'), ('PRICE', 'Price Alert'), ('SYSTEM', 'System Notification'), ('SYSTEM_ERROR', 'System Error'), ('MILESTONE', 'Portfolio Milestone'), ('APP_UPDATE', 'App Update'), ('FUNDING_GOAL', 'Funding Goal Reached'), ('DIVIDEND', 'Dividend Payment'), ('SECURITY', 'Security Alert'), ('MAINTENANCE', 'System Maintenance'), ('NEWS', 'App News'), ('APP_APPROVAL', 'App Approval Status'), ('PAYMENT_PENDING', 'Payment Processing'), ('FUNDING_COMPLETE', 'Funding Complete')], max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name='communityvote',
            unique_together={('user', 'app', 'vote_type')},
        ),
        migrations.AddIndex(
            model_name='communityvote',
            index=models.Index(fields=['user', 'app'], name='core_commun_user_id_642824_idx'),
        ),
    ]

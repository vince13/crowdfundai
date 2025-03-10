# Generated by Django 5.1.5 on 2025-01-27 08:29

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tier', models.CharField(choices=[('FREE', 'Free'), ('DEV_PRO', 'Developer Pro'), ('INV_PRO', 'Investor Pro')], default='FREE', max_length=10)),
                ('start_date', models.DateTimeField(auto_now_add=True)),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('auto_renew', models.BooleanField(default=True)),
                ('last_payment_date', models.DateTimeField(blank=True, null=True)),
                ('next_payment_date', models.DateTimeField(blank=True, null=True)),
                ('payment_method', models.CharField(blank=True, max_length=50, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SubscriptionFeatureUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature_name', models.CharField(max_length=50)),
                ('usage_count', models.IntegerField(default=0)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feature_usage', to='core.subscription')),
            ],
        ),
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['user', 'is_active'], name='core_subscr_user_id_6ccc59_idx'),
        ),
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['tier', 'is_active'], name='core_subscr_tier_2e8aaa_idx'),
        ),
        migrations.AddIndex(
            model_name='subscriptionfeatureusage',
            index=models.Index(fields=['subscription', 'feature_name'], name='core_subscr_subscri_84cd4d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='subscriptionfeatureusage',
            unique_together={('subscription', 'feature_name')},
        ),
    ]

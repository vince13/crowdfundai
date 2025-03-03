from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crowdfund_ai.settings')

app = Celery('crowdfund_ai')

# Load task modules from all registered Django app configs
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure Celery Beat schedule
app.conf.beat_schedule = {
    'check-platform-fees': {
        'task': 'core.tasks.check_platform_fees',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
    },
}

# Auto-discover tasks in all installed apps
app.autodiscover_tasks() 
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

def initialize_monitoring(environment='production'):
    """Initialize monitoring services including Sentry"""
    # Initialize Sentry
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        environment=environment,
        traces_sample_rate=1.0,
        send_default_pii=False,
        before_send=before_send,
    )

def before_send(event, hint):
    """Filter sensitive information before sending to Sentry"""
    if 'request' in event:
        # Remove sensitive headers
        if 'headers' in event['request']:
            sensitive_headers = ['authorization', 'cookie']
            event['request']['headers'] = {
                k: v for k, v in event['request']['headers'].items()
                if k.lower() not in sensitive_headers
            }
        
        # Remove sensitive POST data
        if 'data' in event['request']:
            sensitive_fields = ['password', 'token', 'secret', 'key']
            if isinstance(event['request']['data'], dict):
                event['request']['data'] = {
                    k: '**redacted**' if any(s in k.lower() for s in sensitive_fields) else v
                    for k, v in event['request']['data'].items()
                }
    
    return event 
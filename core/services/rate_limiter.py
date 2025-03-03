from django.core.cache import cache
from django.conf import settings

class NotificationRateLimiter:
    @staticmethod
    def can_send(user_id, notification_type, limit=5, period=3600):
        """Check if user hasn't exceeded notification limit"""
        key = f'notification_rate_{user_id}_{notification_type}'
        count = cache.get(key, 0)
        
        if count >= limit:
            return False
            
        cache.set(key, count + 1, period)
        return True 
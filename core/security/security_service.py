import logging
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('core.security')

class SecurityService:
    @staticmethod
    def detect_suspicious_activity(user, activity_type, details):
        """Log and handle suspicious activity"""
        logger.warning(f"Suspicious activity detected: {activity_type} for user {user.username}. Details: {details}")
        # Implement further actions like notifying admins or locking accounts

    @staticmethod
    def prevent_brute_force(user, max_attempts=5, lockout_time=300):
        """Prevent brute force attacks by locking accounts after too many failed attempts"""
        cache_key = f"login_attempts_{user.id}"
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, timeout=lockout_time)

        if attempts > max_attempts:
            user.is_active = False
            user.save()
            logger.warning(f"User {user.username} has been locked out due to too many failed login attempts.")
            return True

        return False 
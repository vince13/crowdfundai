from django.core.cache import cache
from ..utils import error_response
from django.http import HttpResponse
from django.conf import settings
import time

class HttpResponseTooManyRequests(HttpResponse):
    status_code = 429

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Default rate limits
        self.rate_limits = getattr(settings, 'RATE_LIMITS', {
            'DEFAULT': {'calls': 100, 'period': 60},  # 100 calls per minute
            'API': {'calls': 60, 'period': 60},       # 60 calls per minute for API
            'MONITORING': {'calls': 30, 'period': 60}  # 30 calls per minute for monitoring
        })

    def __call__(self, request):
        if self._should_rate_limit(request):
            rate_limit_key = self._get_rate_limit_key(request)
            if not self._check_rate_limit(rate_limit_key, request):
                return HttpResponseTooManyRequests(
                    "Rate limit exceeded. Please try again later.",
                    content_type="text/plain"
                )
        
        return self.get_response(request)

    def _should_rate_limit(self, request):
        """Determine if request should be rate limited"""
        # Don't rate limit admin users
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.role == 'ADMIN':
                return False

        # Rate limit API and monitoring endpoints
        if request.path.startswith('/api/') or request.path.startswith('/monitoring/'):
            return True

        return False

    def _get_rate_limit_key(self, request):
        """Generate cache key for rate limiting"""
        # Use IP address and path prefix for key
        ip = self._get_client_ip(request)
        if request.path.startswith('/api/'):
            prefix = 'API'
        elif request.path.startswith('/monitoring/'):
            prefix = 'MONITORING'
        else:
            prefix = 'DEFAULT'
        
        return f"rate_limit:{prefix}:{ip}"

    def _check_rate_limit(self, key, request):
        """Check if request is within rate limits"""
        # Determine which rate limit to apply
        if request.path.startswith('/api/'):
            limit = self.rate_limits['API']
        elif request.path.startswith('/monitoring/'):
            limit = self.rate_limits['MONITORING']
        else:
            limit = self.rate_limits['DEFAULT']

        # Get current window from cache
        window = cache.get(key)
        current_time = time.time()

        if window is None:
            # First request in this window
            window = {
                'start_time': current_time,
                'count': 1
            }
            cache.set(key, window, limit['period'])
            return True

        if current_time - window['start_time'] >= limit['period']:
            # Window has expired, start new window
            window = {
                'start_time': current_time,
                'count': 1
            }
            cache.set(key, window, limit['period'])
            return True

        # Check if we're within the limit
        if window['count'] >= limit['calls']:
            return False

        # Increment the counter
        window['count'] += 1
        cache.set(key, window, limit['period'])
        return True

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR') 
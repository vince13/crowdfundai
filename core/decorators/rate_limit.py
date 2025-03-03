from functools import wraps
from django.core.cache import cache
from ..utils import error_response
from django.http import HttpResponse
import time

class HttpResponseTooManyRequests(HttpResponse):
    status_code = 429

def rate_limit(calls=60, period=60, key_prefix='custom'):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Generate cache key
            ip = request.META.get('REMOTE_ADDR')
            key = f"rate_limit:{key_prefix}:{ip}"
            
            # Get current window
            window = cache.get(key)
            current_time = time.time()
            
            if window is None:
                window = {
                    'start_time': current_time,
                    'count': 1
                }
                cache.set(key, window, period)
            elif current_time - window['start_time'] >= period:
                window = {
                    'start_time': current_time,
                    'count': 1
                }
                cache.set(key, window, period)
            elif window['count'] >= calls:
                return HttpResponseTooManyRequests(
                    "Rate limit exceeded. Please try again later.",
                    content_type="text/plain"
                )
            else:
                window['count'] += 1
                cache.set(key, window, period)
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator 
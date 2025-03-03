import time
from typing import Any, Callable
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from collections import defaultdict
import traceback

class PerformanceMonitoringMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Start timing
        start_time = time.time()
        
        # Increment request counter
        request_count = cache.get('request_count', 0)
        cache.set('request_count', request_count + 1, timeout=3600)
        
        try:
            response = self.get_response(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Store overall response time
            response_times = cache.get('response_times', [])
            response_times.append(response_time)
            # Keep only last 1000 response times
            if len(response_times) > 1000:
                response_times = response_times[-1000:]
            cache.set('response_times', response_times, timeout=3600)
            
            # Store per-endpoint response time
            endpoint = f"{request.method} {request.path}"
            endpoint_times = cache.get('endpoint_times', defaultdict(list))
            endpoint_times[endpoint].append(response_time)
            # Keep only last 100 times per endpoint
            if len(endpoint_times[endpoint]) > 100:
                endpoint_times[endpoint] = endpoint_times[endpoint][-100:]
            cache.set('endpoint_times', dict(endpoint_times), timeout=3600)
            
            # Track cache metrics if cache headers present
            if 'X-Cache' in response:
                if response['X-Cache'] == 'HIT':
                    cache.incr('cache_hits', 1)
                else:
                    cache.incr('cache_misses', 1)
            
            return response
            
        except Exception as e:
            # Increment error counter
            error_count = cache.get('error_count', 0)
            cache.set('error_count', error_count + 1, timeout=3600)
            
            # Track error types
            error_type = type(e).__name__
            error_types = cache.get('error_types', defaultdict(int))
            error_types[error_type] += 1
            cache.set('error_types', dict(error_types), timeout=3600)
            
            # Log error details
            error_details = {
                'type': error_type,
                'message': str(e),
                'traceback': traceback.format_exc(),
                'path': request.path,
                'method': request.method,
                'timestamp': time.time()
            }
            
            # Store error details in cache
            recent_errors = cache.get('recent_errors', [])
            recent_errors.append(error_details)
            # Keep only last 50 errors
            if len(recent_errors) > 50:
                recent_errors = recent_errors[-50:]
            cache.set('recent_errors', recent_errors, timeout=3600)
            
            raise  # Re-raise the exception after logging 
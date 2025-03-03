import time
import logging
from ..models_view.api import APIRequest, APIError
from django.core.cache import cache
from django.utils import timezone
import traceback

logger = logging.getLogger('core.api.monitoring')

class APIMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = self.get_response(request)

            # Record request
            self._record_request(request, response, start_time)

            return response
        except Exception as e:
            # Record error
            self._record_error(request, e, start_time)
            
            # Enhanced error tracking
            error_details = {
                'type': e.__class__.__name__,
                'message': str(e),
                'traceback': traceback.format_exc(),
                'user_id': request.user.id if request.user.is_authenticated else None,
                'endpoint': request.path,
                'method': request.method,
                'timestamp': timezone.now()
            }
            
            # Store in cache for real-time monitoring
            self._update_error_stats(error_details)
            
            raise

    def _record_request(self, request, response, start_time):
        """Record API request details"""
        try:
            APIRequest.objects.create(
                user=request.user if request.user.is_authenticated else None,
                endpoint=request.path,
                method=request.method,
                response_time=(time.time() - start_time) * 1000,  # Convert to ms
                status_code=response.status_code,
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception as e:
            logger.error(f"Error recording API request: {str(e)}")

    def _record_error(self, request, exception, start_time):
        """Record API error details"""
        try:
            api_request = APIRequest.objects.create(
                user=request.user if request.user.is_authenticated else None,
                endpoint=request.path,
                method=request.method,
                response_time=(time.time() - start_time) * 1000,
                status_code=500,
                ip_address=request.META.get('REMOTE_ADDR')
            )

            APIError.objects.create(
                request=api_request,
                error_type=exception.__class__.__name__,
                error_message=str(exception),
                stack_trace=getattr(exception, '__traceback__', None)
            )
        except Exception as e:
            logger.error(f"Error recording API error: {str(e)}") 

    def _update_error_stats(self, error_details):
        with cache.lock('api_error_stats'):
            stats = cache.get('api_error_stats', {
                'count': 0,
                'types': {},
                'recent': []
            })
            
            stats['count'] += 1
            stats['types'][error_details['type']] = (
                stats['types'].get(error_details['type'], 0) + 1
            )
            
            stats['recent'].append(error_details)
            if len(stats['recent']) > 50:
                stats['recent'] = stats['recent'][-50:]
                
            cache.set('api_error_stats', stats, timeout=3600) 
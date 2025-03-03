from django.utils.deprecation import MiddlewareMixin
import requests
from django.core.cache import cache
from redis.exceptions import ConnectionError as RedisConnectionError
from django_redis.exceptions import ConnectionInterrupted

class CurrencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip for admin URLs
        if request.path.startswith('/admin/'):
            return None
            
        # During development or if there's a Redis error, use NGN
        if request.META.get('SERVER_NAME') in ['localhost', '127.0.0.1']:
            request.currency = 'NGN'
            return None
            
        # Check cache first
        client_ip = self.get_client_ip(request)
        cache_key = f'currency_for_ip_{client_ip}'
        
        try:
            currency = cache.get(cache_key)
        except (RedisConnectionError, ConnectionInterrupted):
            # If Redis is not available, default to NGN
            request.currency = 'NGN'
            return None
        
        if currency is None:
            try:
                # Use a free IP geolocation service
                response = requests.get(f'https://ipapi.co/{client_ip}/json/')
                data = response.json()
                
                # Set NGN for Nigeria, USD for others
                currency = 'NGN' if data.get('country_code') == 'NG' else 'USD'
                
                try:
                    # Try to cache for 24 hours
                    cache.set(cache_key, currency, 86400)
                except (RedisConnectionError, ConnectionInterrupted):
                    # If Redis is not available, just continue without caching
                    pass
            except Exception:
                # Default to NGN in case of any error
                currency = 'NGN'
        
        request.currency = currency
        return None
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR') 
from django.http import HttpResponseForbidden
from django.conf import settings
from ..services.security import SecurityService
from django.middleware.csrf import get_token
import logging

logger = logging.getLogger('core.security')

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ensure CSRF token is generated early
        if request.method == 'GET':
            get_token(request)
        
        # Process the request
        response = self.get_response(request)

        # Add security headers
        security_headers = SecurityService.get_security_headers()
        for header, value in security_headers.items():
            response[header] = value

        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Process view-level security checks
        """
        # Skip security checks for static files and certain paths
        if hasattr(view_func, 'csrf_exempt'):
            return None

        # Skip additional security checks in development
        if settings.DEBUG:
            return None

        return None

class SecureProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only set secure headers in production
        if not settings.DEBUG:
            # Check if we're behind a proxy
            if 'HTTP_X_FORWARDED_PROTO' in request.META:
                if request.META['HTTP_X_FORWARDED_PROTO'] == 'https':
                    request.is_secure = lambda: True

            # Set the remote address properly
            if 'HTTP_X_FORWARDED_FOR' in request.META:
                real_ip = request.META['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
                request.META['REMOTE_ADDR'] = real_ip

        response = self.get_response(request)
        return response 
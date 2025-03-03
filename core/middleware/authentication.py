from django.http import JsonResponse
from django.conf import settings
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
import jwt
from datetime import datetime
import logging

logger = logging.getLogger('core.security')

class APIAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.public_paths = [
            '/api/v1/auth/register/',
            '/api/v1/auth/login/',
            '/api/v1/auth/verify-email/',
            '/api/v1/docs/',
            '/api/v1/redoc/',
            '/api/check-session/',
            '/api/apps/',  # Allow public access to app-related endpoints
        ]
        # Endpoints that can use session authentication
        self.session_auth_paths = [
            '/api/blog/generate-content/',  # Non-versioned endpoint
            '/api/v1/blog/generate-content/',  # Versioned endpoint
            '/api/v1/auth/setup-2fa/',
            '/api/v1/auth/verify-2fa-setup/',
            '/api/v1/auth/disable-2fa/',
            '/api/v1/auth/signout-all-devices/',
            '/api/v1/auth/delete-account/',
            '/api/v1/auth/logout/',
            '/api/portfolio/stats/'  # Add portfolio stats endpoint
        ]

    def __call__(self, request):
        logger.info(f"Processing request for path: {request.path}")
        logger.info(f"User authenticated: {request.user.is_authenticated}")
        logger.info(f"Is staff: {request.user.is_staff if request.user.is_authenticated else 'N/A'}")
        
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Allow unauthenticated access to public endpoints
        if any(request.path.startswith(path) for path in self.public_paths):
            logger.info(f"Public path: {request.path}")
            return self.get_response(request)
            
        # Allow session authentication for specific endpoints
        if any(request.path.startswith(path) for path in self.session_auth_paths):
            logger.info(f"Session auth path: {request.path}")
            if request.user and request.user.is_authenticated:
                logger.info("User is authenticated, allowing request")
                return self.get_response(request)
            logger.warning("User is not authenticated for session auth path")
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'authentication_required'
            }, status=401)

        try:
            # Check for token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'authentication_required'
                }, status=401)

            # Validate token format
            try:
                auth_type, token = auth_header.split(' ')
                if auth_type.lower() != 'bearer':
                    raise ValueError('Invalid authentication type')
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid authentication format',
                    'code': 'invalid_auth_format'
                }, status=401)

            # Verify JWT token
            try:
                payload = jwt.decode(
                    token, 
                    settings.JWT_SECRET_KEY,
                    algorithms=['HS256']
                )
                
                # Check token expiration
                exp_timestamp = payload.get('exp')
                if not exp_timestamp or datetime.fromtimestamp(exp_timestamp) < datetime.now():
                    raise jwt.ExpiredSignatureError('Token has expired')
                
                # Add user to request
                request.user_id = payload.get('user_id')
                request.user_role = payload.get('role')
                
                # Log successful authentication
                logger.info(f"API Authentication successful for user {request.user_id}")
                
            except jwt.ExpiredSignatureError:
                return JsonResponse({
                    'error': 'Token has expired',
                    'code': 'token_expired'
                }, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({
                    'error': 'Invalid token',
                    'code': 'invalid_token'
                }, status=401)

            # Continue with the request
            response = self.get_response(request)
            return response

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return JsonResponse({
                'error': 'Authentication failed',
                'code': 'auth_failed'
            }, status=401) 
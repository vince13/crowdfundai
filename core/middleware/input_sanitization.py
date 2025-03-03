import re
import html
import json
import logging
from django.http import JsonResponse
from django.core.exceptions import ValidationError

logger = logging.getLogger('core.security')

class InputSanitizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns for common malicious patterns
        self.sql_injection_pattern = re.compile(r'(\b(select|insert|update|delete|drop|union|exec)\b)', re.IGNORECASE)
        self.xss_pattern = re.compile(r'<[^>]*script|javascript:|data:|vbscript:', re.IGNORECASE)
        self.path_traversal_pattern = re.compile(r'\.\./')

    def __call__(self, request):
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        try:
            # Sanitize query parameters
            if request.GET:
                self._sanitize_querydict(request.GET)

            # Sanitize POST data
            if request.POST:
                self._sanitize_querydict(request.POST)

            # Sanitize JSON data
            if request.content_type == 'application/json':
                if request.body:
                    try:
                        json_data = json.loads(request.body)
                        sanitized_data = self._sanitize_json(json_data)
                        request._body = json.dumps(sanitized_data).encode('utf-8')
                    except json.JSONDecodeError:
                        return JsonResponse({
                            'error': 'Invalid JSON format',
                            'code': 'invalid_json'
                        }, status=400)

            # Continue with the request
            response = self.get_response(request)
            return response

        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return JsonResponse({
                'error': str(e),
                'code': 'validation_error'
            }, status=400)
        except Exception as e:
            logger.error(f"Input sanitization error: {str(e)}")
            return JsonResponse({
                'error': 'Invalid input data',
                'code': 'invalid_input'
            }, status=400)

    def _sanitize_querydict(self, query_dict):
        """Sanitize Django QueryDict objects"""
        for key in query_dict.keys():
            values = query_dict.getlist(key)
            sanitized_values = [self._sanitize_string(value) for value in values]
            query_dict.setlist(key, sanitized_values)

    def _sanitize_json(self, data):
        """Recursively sanitize JSON data"""
        if isinstance(data, dict):
            return {key: self._sanitize_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_json(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data)
        return data

    def _sanitize_string(self, value):
        """Sanitize a single string value"""
        if not isinstance(value, str):
            return value

        # Check for SQL injection attempts
        if self.sql_injection_pattern.search(value):
            raise ValidationError('Potential SQL injection detected')

        # Check for XSS attempts
        if self.xss_pattern.search(value):
            raise ValidationError('Potential XSS attack detected')

        # Check for path traversal attempts
        if self.path_traversal_pattern.search(value):
            raise ValidationError('Path traversal attempt detected')

        # HTML escape the value
        sanitized = html.escape(value)

        # Additional custom sanitization rules can be added here
        
        return sanitized 
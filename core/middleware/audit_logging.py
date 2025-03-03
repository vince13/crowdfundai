import json
import logging
import uuid
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.db import models

logger = logging.getLogger('core.audit')

class AuditLog(models.Model):
    class EventType(models.TextChoices):
        AUTH = 'AUTH', 'Authentication'
        ACCESS = 'ACCESS', 'Resource Access'
        MODIFY = 'MODIFY', 'Data Modification'
        DELETE = 'DELETE', 'Data Deletion'
        ADMIN = 'ADMIN', 'Admin Action'
        SECURITY = 'SECURITY', 'Security Event'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    user_id = models.CharField(max_length=100, null=True)
    ip_address = models.GenericIPAddressField()
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    request_data = models.JSONField(null=True)
    response_status = models.IntegerField()
    user_agent = models.TextField()
    session_id = models.CharField(max_length=100, null=True)
    additional_data = models.JSONField(null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp', 'event_type']),
            models.Index(fields=['user_id', 'event_type']),
            models.Index(fields=['endpoint', 'method']),
        ]

class AuditLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate unique request ID
        request.audit_id = str(uuid.uuid4())
        
        # Start timing the request
        start_time = timezone.now()
        
        # Get the response
        response = self.get_response(request)
        
        # Log the request/response
        self._log_event(request, response, start_time)
        
        return response
    
    def _log_event(self, request, response, start_time):
        try:
            # Determine event type based on request
            event_type = self._determine_event_type(request)
            
            # Extract request data safely
            request_data = self._extract_request_data(request)
            
            # Get user ID if available
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user'):
                user_id = request.user.id if request.user.is_authenticated else None
            
            # Create audit log entry
            AuditLog.objects.create(
                event_type=event_type,
                user_id=user_id,
                ip_address=self._get_client_ip(request),
                endpoint=request.path,
                method=request.method,
                request_data=request_data,
                response_status=response.status_code,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                session_id=request.session.session_key,
                additional_data={
                    'duration_ms': (timezone.now() - start_time).total_seconds() * 1000,
                    'request_id': request.audit_id,
                    'headers': dict(request.headers),
                    'query_params': dict(request.GET),
                }
            )
            
        except Exception as e:
            logger.error(f"Error in audit logging: {str(e)}")
    
    def _determine_event_type(self, request):
        """Determine the type of event based on the request"""
        if 'login' in request.path or 'logout' in request.path:
            return AuditLog.EventType.AUTH
        elif request.method in ['POST', 'PUT', 'PATCH']:
            return AuditLog.EventType.MODIFY
        elif request.method == 'DELETE':
            return AuditLog.EventType.DELETE
        elif '/admin/' in request.path:
            return AuditLog.EventType.ADMIN
        return AuditLog.EventType.ACCESS
    
    def _extract_request_data(self, request):
        """Safely extract request data for logging"""
        try:
            if request.content_type == 'application/json':
                if request.body:
                    data = json.loads(request.body)
                    # Sanitize sensitive data
                    if isinstance(data, dict):
                        data = self._sanitize_sensitive_data(data)
                    return data
            elif request.POST:
                return self._sanitize_sensitive_data(dict(request.POST))
            return None
        except Exception:
            return None
    
    def _sanitize_sensitive_data(self, data):
        """Remove sensitive information from request data"""
        sensitive_fields = {'password', 'token', 'secret', 'credit_card', 'api_key'}
        
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_fields):
                    sanitized[key] = '[REDACTED]'
                else:
                    sanitized[key] = self._sanitize_sensitive_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_sensitive_data(item) for item in data]
        return data
    
    def _get_client_ip(self, request):
        """Get the client's IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR') 
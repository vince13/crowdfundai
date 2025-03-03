from django.conf import settings
from django.core.exceptions import ValidationError
import re
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from ..models import SecurityAuditLog

logger = logging.getLogger('core.security')

class SecurityService:
    # Password Policy Constants
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    PASSWORD_EXPIRY_DAYS = 90
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # Input Validation Patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,32}$')
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?@#$%^&*()+=\[\]{}|:;<>~`\'\"\/\\]+$')

    @classmethod
    def validate_password(cls, password, user=None):
        """
        Validate password strength
        """
        try:
            if len(password) < cls.MIN_PASSWORD_LENGTH:
                raise ValidationError(f'Password must be at least {cls.MIN_PASSWORD_LENGTH} characters long')
            
            if len(password) > cls.MAX_PASSWORD_LENGTH:
                raise ValidationError(f'Password cannot exceed {cls.MAX_PASSWORD_LENGTH} characters')
            
            if not any(char.isupper() for char in password):
                raise ValidationError('Password must contain at least one uppercase letter')
                
            if not any(char.islower() for char in password):
                raise ValidationError('Password must contain at least one lowercase letter')
                
            if not any(char.isdigit() for char in password):
                raise ValidationError('Password must contain at least one number')
                
            if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?' for char in password):
                raise ValidationError('Password must contain at least one special character')
            
            if user and user.username.lower() in password.lower():
                raise ValidationError('Password cannot contain username')
            
            return True, None
            
        except ValidationError as e:
            return False, str(e)

    @classmethod
    def generate_secure_token(cls, length=32):
        """
        Generate a cryptographically secure token
        """
        return secrets.token_urlsafe(length)

    @classmethod
    def hash_sensitive_data(cls, data):
        """
        Hash sensitive data using SHA-256
        """
        return hashlib.sha256(str(data).encode()).hexdigest()

    @classmethod
    def sanitize_input(cls, input_string, input_type='text'):
        """
        Sanitize user input based on type
        """
        if input_string is None:
            return None
            
        input_string = str(input_string).strip()
        
        if input_type == 'email':
            if not cls.EMAIL_PATTERN.match(input_string):
                raise ValidationError('Invalid email format')
                
        elif input_type == 'username':
            if not cls.USERNAME_PATTERN.match(input_string):
                raise ValidationError('Username must be 3-32 characters and contain only letters, numbers, underscores, and hyphens')
                
        elif input_type == 'text':
            if not cls.SAFE_STRING_PATTERN.match(input_string):
                raise ValidationError('Input contains invalid characters')
        
        return input_string

    @classmethod
    def validate_session_security(cls, request):
        """
        Validate session security settings
        """
        # Skip checks in development
        if settings.DEBUG:
            return True, None
        
        # Check if session is secure
        if not request.is_secure():
            logger.warning('Insecure session detected')
            return False, 'Insecure connection'
        
        # Check session expiry
        session_age = request.session.get('_session_init_timestamp_')
        if session_age:
            age = datetime.now() - datetime.fromtimestamp(session_age)
            if age > timedelta(hours=12):  # 12-hour session timeout
                logger.info('Session expired')
                return False, 'Session expired'
            
        return True, None

    @classmethod
    def get_security_headers(cls):
        """
        Get recommended security headers
        """
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
        }
        
        # Add stricter headers in production
        if not settings.DEBUG:
            headers.update({
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
                'Content-Security-Policy': (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data:; "
                    "connect-src 'self'"
                ),
                'Referrer-Policy': 'strict-origin-when-cross-origin',
                'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
            })
        
        return headers

    @classmethod
    def check_rate_limit(cls, key, max_attempts, duration):
        """
        Check rate limiting
        """
        from django.core.cache import cache
        
        attempts = cache.get(key, 0)
        
        if attempts >= max_attempts:
            return False, f'Rate limit exceeded. Try again in {duration} minutes'
            
        cache.set(key, attempts + 1, duration * 60)  # Convert minutes to seconds
        return True, None

    @classmethod
    def audit_log(cls, user, action, status, details=None):
        """
        Log security-related events
        """
        from ..models_view.audit import SecurityAuditLog
        
        try:
            SecurityAuditLog.objects.create(
                user=user,
                action=action,
                status=status,
                details=details
            )
        except Exception as e:
            logger.error(f'Failed to create audit log: {str(e)}') 
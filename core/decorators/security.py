from functools import wraps
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from ..services.security import SecurityService
import logging

logger = logging.getLogger('core.security')

def require_secure_transport(view_func):
    """Ensure request is made over HTTPS"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.is_secure():
            logger.warning(f'Insecure request to {request.path} from {request.META.get("REMOTE_ADDR")}')
            return HttpResponseForbidden('HTTPS is required')
        return view_func(request, *args, **kwargs)
    return wrapper

def validate_input(input_type='text'):
    """Validate and sanitize input parameters"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Validate POST data
                if request.method == 'POST':
                    for key, value in request.POST.items():
                        SecurityService.sanitize_input(value, input_type)
                
                # Validate GET parameters
                for key, value in request.GET.items():
                    SecurityService.sanitize_input(value, input_type)
                    
                return view_func(request, *args, **kwargs)
            except Exception as e:
                logger.warning(f'Input validation failed: {str(e)}')
                return HttpResponseForbidden('Invalid input detected')
        return wrapper
    return decorator

def require_password_change(view_func):
    """Force password change if password is expired"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.password_change_required:
                logger.info(f'Password change required for user {request.user}')
                return redirect('core:change_password')
        return view_func(request, *args, **kwargs)
    return wrapper

def audit_view(action_name):
    """Audit log decorator for views"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                response = view_func(request, *args, **kwargs)
                status = 'success' if response.status_code < 400 else 'failure'
                
                SecurityService.audit_log(
                    user=request.user if request.user.is_authenticated else None,
                    action=action_name,
                    status=status,
                    details={
                        'path': request.path,
                        'method': request.method,
                        'ip': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT')
                    }
                )
                return response
            except Exception as e:
                logger.error(f'Error in {action_name}: {str(e)}')
                raise
        return wrapper
    return decorator 
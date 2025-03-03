from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging
import traceback

logger = logging.getLogger('core.api')

def custom_exception_handler(exc, context):
    """Enhanced exception handler with better error tracking"""
    response = exception_handler(exc, context)
    
    if response is None:
        # Handle uncaught exceptions
        response = Response({
            'error': str(exc),
            'type': exc.__class__.__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Add additional error details
    response.data['status_code'] = response.status_code
    response.data['type'] = exc.__class__.__name__
    
    # Enhanced error logging
    logger.error(
        f"API Error: {str(exc)}",
        exc_info=True,
        extra={
            'view': context['view'].__class__.__name__,
            'status_code': response.status_code,
            'error_type': exc.__class__.__name__,
            'traceback': traceback.format_exc()
        }
    )
    
    return response 
from django.utils import timezone
from core.models import UserActivity

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Track certain activities based on the path
            if request.path.startswith('/apps/'):
                activity_type = 'VIEW_APP'
                description = f'Viewed app page: {request.path}'
            elif request.path.startswith('/analytics/'):
                activity_type = 'VIEW_ANALYTICS'
                description = f'Viewed analytics page: {request.path}'
            else:
                return response
            
            UserActivity.objects.create(
                user=request.user,
                activity_type=activity_type,
                description=description,
                ip_address=self.get_client_ip(request),
                metadata={
                    'path': request.path,
                    'method': request.method,
                }
            )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip 
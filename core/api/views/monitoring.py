from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from django.db.models import Avg, Count
from ...models import APIRequest, APIError
from ..serializers import APIRequestSerializer, APIErrorSerializer
import logging
from core.decorators.rate_limit import rate_limit
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from core.services.blog_generator import BlogGenerator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from core.services.monitoring import SystemMetricsService

logger = logging.getLogger('core.api.monitoring')

class APIMonitoringViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get API usage statistics"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        stats = {
            'total_requests': APIRequest.objects.count(),
            'recent_requests': APIRequest.objects.filter(timestamp__gte=last_24h).count(),
            'error_rate': self._calculate_error_rate(),
            'average_response_time': self._calculate_avg_response_time(),
            'endpoint_usage': self._get_endpoint_usage(),
            'recent_errors': self._get_recent_errors()
        }
        
        return Response(stats)

    def _calculate_error_rate(self):
        """Calculate API error rate"""
        total = APIRequest.objects.count()
        if total == 0:
            return 0
        errors = APIError.objects.count()
        return (errors / total) * 100

    def _calculate_avg_response_time(self):
        """Calculate average API response time"""
        return APIRequest.objects.aggregate(
            avg_time=Avg('response_time')
        )['avg_time'] or 0

    def _get_endpoint_usage(self):
        """Get endpoint usage statistics"""
        return APIRequest.objects.values('endpoint').annotate(
            count=Count('id')
        ).order_by('-count')

    def _get_recent_errors(self):
        """Get recent API errors"""
        return APIError.objects.order_by('-timestamp')[:10] 

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@rate_limit(calls=30, period=60, key_prefix='api_metrics')
def get_metrics(request):
    """API endpoint to get system metrics"""
    metrics = SystemMetricsService.get_system_metrics()
    return JsonResponse(metrics)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_blog_content(request):
    """API endpoint to generate blog content from a URL"""
    try:
        source_url = request.data.get('source_url')
        if not source_url:
            return JsonResponse({'error': 'source_url is required'}, status=400)
            
        generator = BlogGenerator()
        content = generator.generate_from_url(source_url)
        return JsonResponse({'content': content})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 
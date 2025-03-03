from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..serializers import NotificationSerializer
from ...models import Notification
from django.utils import timezone

class NotificationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing notifications
    """
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        """Filter notifications for the current user"""
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'success'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        self.get_queryset().update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'status': 'success'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count}) 
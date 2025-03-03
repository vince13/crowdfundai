from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from ..serializers import (
    AppAnalyticsSerializer,
    InvestmentAnalyticsSerializer,
    PlatformAnalyticsSerializer
)
from ...models import AppListing, Investment
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

class AnalyticsViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def platform_stats(self, request):
        """Get platform-wide statistics"""
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        stats = {
            'total_apps': AppListing.objects.count(),
            'total_investments': Investment.objects.count(),
            'total_funding': Investment.objects.aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'active_users': Investment.objects.values('investor').distinct().count(),
            'recent_activity': {
                'new_apps': AppListing.objects.filter(
                    created_at__gte=last_30_days
                ).count(),
                'new_investments': Investment.objects.filter(
                    created_at__gte=last_30_days
                ).count()
            },
            'growth_metrics': {
                'funding_growth': self._calculate_growth_rate('amount'),
                'user_growth': self._calculate_growth_rate('investor')
            }
        }
        
        serializer = PlatformAnalyticsSerializer(stats)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def app_performance(self, request, pk=None):
        """Get detailed app performance metrics"""
        app = AppListing.objects.get(pk=pk)
        
        metrics = {
            'total_investments': app.investments.count(),
            'total_funding': app.investments.aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'average_investment': app.investments.aggregate(
                avg=Avg('amount')
            )['avg'] or 0,
            'investor_count': app.investments.values('investor').distinct().count(),
            'funding_progress': (app.current_funding / app.funding_goal) * 100,
            'daily_investments': self._get_daily_investments(app)
        }
        
        serializer = AppAnalyticsSerializer(metrics)
        return Response(serializer.data)

    def _calculate_growth_rate(self, field):
        """Calculate growth rate for a given field"""
        now = timezone.now()
        last_month = now - timedelta(days=30)
        two_months_ago = now - timedelta(days=60)
        
        current = Investment.objects.filter(created_at__gte=last_month).aggregate(
            total=Sum(field)
        )['total'] or 0
        
        previous = Investment.objects.filter(
            created_at__gte=two_months_ago,
            created_at__lt=last_month
        ).aggregate(total=Sum(field))['total'] or 0
        
        if previous == 0:
            return 100 if current > 0 else 0
        
        return ((current - previous) / previous) * 100

    def _get_daily_investments(self, app):
        """Get daily investment totals for an app"""
        last_30_days = timezone.now() - timedelta(days=30)
        daily_investments = (
            app.investments
            .filter(created_at__gte=last_30_days)
            .extra({'date': "date(created_at)"})
            .values('date')
            .annotate(total=Sum('amount'))
            .order_by('date')
        )
        
        return {
            str(item['date']): item['total']
            for item in daily_investments
        } 
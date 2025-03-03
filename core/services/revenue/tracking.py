from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from core.models import Revenue, AppListing, Distribution
from datetime import datetime, timedelta

class RevenueTrackingService:
    def record_revenue(self, app, amount, source, description=None, period_start=None, period_end=None):
        """Record a new revenue entry for an app"""
        if not isinstance(app, AppListing):
            raise ValueError("Invalid app instance provided")
            
        if not isinstance(amount, (int, float, Decimal)):
            raise ValueError("Amount must be a numeric value")
            
        revenue = Revenue.objects.create(
            app=app,
            amount=Decimal(str(amount)),
            currency='NGN',  # Explicitly set currency to NGN
            source=source,
            description=description,
            period_start=period_start or timezone.now(),
            period_end=period_end or timezone.now(),
            is_distributed=False
        )
        return revenue
        
    def get_total_revenue(self, app, start_date=None, end_date=None):
        """Get total revenue for an app within date range"""
        revenues = Revenue.objects.filter(app=app)
        
        if start_date:
            revenues = revenues.filter(created_at__gte=start_date)
        if end_date:
            revenues = revenues.filter(created_at__lte=end_date)
            
        total = revenues.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return total
        
    def get_monthly_revenue(self, app, months=12):
        """Get monthly revenue breakdown for the last N months"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30 * months)
        
        revenues = Revenue.objects.filter(
            app=app,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).order_by('created_at')
        
        monthly_data = {}
        for revenue in revenues:
            month_key = revenue.created_at.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = Decimal('0')
            monthly_data[month_key] += revenue.amount
            
        return monthly_data
        
    def get_pending_distributions(self, app):
        """Get total pending distributions for an app"""
        return Revenue.objects.filter(
            app=app,
            is_distributed=False,
            distributions__isnull=True  # No distribution attempts yet
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
    def get_failed_distributions(self, app):
        """Get total failed distributions for an app"""
        return Distribution.objects.filter(
            revenue__app=app,
            status='FAILED'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0') 
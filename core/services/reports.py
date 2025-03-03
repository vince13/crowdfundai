from django.http import HttpResponse
from django.utils import timezone
from django.db import models
from django.db.models.functions import TruncMonth
from ..models import Investment, AppListing, User
import csv
from io import StringIO

class ReportGenerator:
    @staticmethod
    def generate_investment_report(user, start_date, end_date):
        """Generate a CSV report of user investments within the date range"""
        investments = Investment.objects.filter(
            investor=user,
            created_at__range=[start_date, end_date]
        ).select_related('app')

        # Create CSV file
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'App', 'Amount', 'Status'])

        for investment in investments:
            writer.writerow([
                investment.created_at.strftime('%Y-%m-%d'),
                investment.app.name,
                f"${investment.amount}",
                investment.status
            ])

        # Create the HTTP response with CSV content
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="investment_report_{start_date}_to_{end_date}.csv"'
        return response

    @staticmethod
    def generate_platform_stats():
        """Generate platform-wide statistics report for admins"""
        # Get basic stats
        total_users = User.objects.count()
        total_apps = AppListing.objects.count()
        total_investments = Investment.objects.count()
        total_investment_amount = Investment.objects.filter(status='COMPLETED').aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        # Get monthly stats for the last 12 months
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=365)
        monthly_stats = Investment.objects.filter(
            created_at__range=[start_date, end_date],
            status='COMPLETED'
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=models.Sum('amount'),
            count=models.Count('id')
        ).order_by('month')

        # Create CSV file
        output = StringIO()
        writer = csv.writer(output)
        
        # Write summary stats
        writer.writerow(['Platform Statistics'])
        writer.writerow(['Total Users', total_users])
        writer.writerow(['Total Apps', total_apps])
        writer.writerow(['Total Investments', total_investments])
        writer.writerow(['Total Investment Amount', f"${total_investment_amount}"])
        writer.writerow([])
        
        # Write monthly stats
        writer.writerow(['Monthly Statistics'])
        writer.writerow(['Month', 'Number of Investments', 'Total Amount'])
        for stat in monthly_stats:
            writer.writerow([
                stat['month'].strftime('%Y-%m'),
                stat['count'],
                f"${stat['total']}"
            ])

        # Create the HTTP response with CSV content
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="platform_stats.csv"'
        return response 
from django.db.models import Sum, Count, F, Q, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, ExtractYear
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from ..models import EscrowTransaction, AppListing, ProjectMilestone, Investment, User
import pandas as pd
import logging
import csv
from django.http import HttpResponse

logger = logging.getLogger(__name__)

class EscrowReportingService:
    @staticmethod
    def get_transaction_history(app: AppListing, start_date=None, end_date=None):
        """Get detailed transaction history for an app."""
        transactions = EscrowTransaction.objects.filter(app=app)
        
        if start_date:
            transactions = transactions.filter(created_at__gte=start_date)
        if end_date:
            transactions = transactions.filter(created_at__lte=end_date)
            
        return transactions.select_related(
            'milestone', 'investor', 'original_transaction'
        ).order_by('-created_at')

    @staticmethod
    def get_milestone_performance(app: AppListing):
        """Get milestone completion and release statistics."""
        milestones = ProjectMilestone.objects.filter(app=app)
        
        stats = []
        for milestone in milestones:
            releases = EscrowTransaction.objects.filter(
                app=app,
                milestone=milestone,
                transaction_type='MILESTONE_RELEASE',
                status='COMPLETED'
            )
            
            total_released = releases.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            stats.append({
                'milestone': milestone,
                'status': milestone.status,
                'progress': milestone.progress,
                'target_date': milestone.target_date,
                'completion_date': milestone.completion_date,
                'release_percentage': milestone.release_percentage,
                'total_released': total_released,
                'deliverables_status': milestone.get_deliverables_status()
            })
            
        return stats

    @staticmethod
    def get_dispute_analytics(app: AppListing):
        """Get dispute statistics and trends."""
        disputes = EscrowTransaction.objects.filter(
            app=app,
            dispute_status__in=['PENDING', 'RESOLVED_RELEASE', 'RESOLVED_REFUND']
        )
        
        total_disputes = disputes.count()
        resolved_disputes = disputes.exclude(dispute_status='PENDING').count()
        resolution_time = timedelta(days=0)
        
        if resolved_disputes:
            resolved = disputes.exclude(dispute_status='PENDING')
            total_time = sum(
                (d.dispute_resolved_by.last_login - d.created_at).days 
                for d in resolved
            )
            resolution_time = timedelta(days=total_time / resolved_disputes)
        
        return {
            'total_disputes': total_disputes,
            'pending_disputes': total_disputes - resolved_disputes,
            'resolved_disputes': resolved_disputes,
            'avg_resolution_time': resolution_time,
            'resolution_breakdown': {
                'released': disputes.filter(dispute_status='RESOLVED_RELEASE').count(),
                'refunded': disputes.filter(dispute_status='RESOLVED_REFUND').count()
            }
        }

    @staticmethod
    def generate_monthly_report(app: AppListing, year: int, month: int):
        """Generate a monthly escrow activity report."""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
            
        transactions = EscrowTransaction.objects.filter(
            app=app,
            created_at__gte=start_date,
            created_at__lt=end_date
        )
        
        # Transaction summary
        summary = {
            'deposits': transactions.filter(
                transaction_type='DEPOSIT'
            ).aggregate(
                count=Count('id'),
                total=Sum('amount')
            ),
            'releases': transactions.filter(
                transaction_type__in=['RELEASE', 'MILESTONE_RELEASE']
            ).aggregate(
                count=Count('id'),
                total=Sum('amount')
            ),
            'refunds': transactions.filter(
                transaction_type__in=['REFUND', 'PARTIAL_REFUND']
            ).aggregate(
                count=Count('id'),
                total=Sum('amount')
            )
        }
        
        # Milestone progress
        milestones = ProjectMilestone.objects.filter(
            app=app,
            target_date__gte=start_date,
            target_date__lt=end_date
        )
        
        milestone_summary = []
        for milestone in milestones:
            milestone_summary.append({
                'title': milestone.title,
                'status': milestone.status,
                'progress': milestone.progress,
                'release_percentage': milestone.release_percentage,
                'total_released': transactions.filter(
                    milestone=milestone,
                    transaction_type='MILESTONE_RELEASE'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            })
        
        # Dispute activity
        disputes = transactions.exclude(dispute_status='NO_DISPUTE')
        dispute_summary = {
            'new_disputes': disputes.filter(
                dispute_status='PENDING'
            ).count(),
            'resolved_disputes': disputes.exclude(
                dispute_status='PENDING'
            ).count(),
            'total_disputed_amount': disputes.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        }
        
        return {
            'period': {
                'year': year,
                'month': month,
                'start_date': start_date,
                'end_date': end_date
            },
            'transaction_summary': summary,
            'milestone_summary': milestone_summary,
            'dispute_summary': dispute_summary,
            'ending_balance': app.funds_in_escrow
        }

    @staticmethod
    def export_transaction_history(app: AppListing, start_date=None, end_date=None):
        """Export transaction history to a pandas DataFrame."""
        transactions = EscrowReportingService.get_transaction_history(
            app, start_date, end_date
        )
        
        data = []
        for tx in transactions:
            data.append({
                'transaction_id': tx.id,
                'type': tx.get_transaction_type_display(),
                'amount': tx.amount,
                'currency': tx.currency,
                'status': tx.get_status_display(),
                'investor': tx.investor.email,
                'payment_gateway': tx.payment_gateway,
                'gateway_reference': tx.gateway_reference,
                'milestone': tx.milestone.title if tx.milestone else None,
                'dispute_status': tx.get_dispute_status_display(),
                'created_at': tx.created_at,
                'completed_at': tx.completed_at
            })
            
        return pd.DataFrame(data)

    @staticmethod
    def generate_investment_report(user, start_date, end_date):
        """Generate a CSV report of investments for a user within a date range"""
        investments = Investment.objects.filter(
            investor=user,
            created_at__range=(start_date, end_date)
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="investment_report_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'App', 'Amount', 'Status'])

        for investment in investments:
            writer.writerow([investment.created_at, investment.app.name, investment.amount_paid, investment.status])

        return response

    @staticmethod
    def generate_platform_stats():
        """Generate a CSV report of platform statistics"""
        total_users = User.objects.count()
        total_investments = Investment.objects.count()
        total_investment_amount = Investment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="platform_stats_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Users', total_users])
        writer.writerow(['Total Investments', total_investments])
        writer.writerow(['Total Investment Amount', total_investment_amount])

        return response 
from datetime import datetime
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.db import transaction
from core.models import Revenue, Distribution, ShareOwnership, Transaction, AppListing
from decimal import Decimal
from django.core.exceptions import ValidationError

class RevenueDistributionService:
    def get_total_revenue(self, user, app_id=None, currency='USD'):
        """Get total revenue for all apps of a user or a specific app"""
        revenues = Revenue.objects.all()
        
        if app_id:
            revenues = revenues.filter(app_id=app_id)
        else:
            revenues = revenues.filter(app__developer=user)
            
        if currency == 'USD':
            # Convert all revenues to USD
            total = sum(revenue.get_amount_usd() for revenue in revenues)
        else:
            # Only sum revenues in specified currency
            total = revenues.filter(currency=currency).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
        return Decimal(str(total))
    
    def get_monthly_revenue(self, user, app_id=None, currency='USD'):
        """Get revenue for the current month"""
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        revenues = Revenue.objects.filter(created_at__gte=start_of_month)
        
        if app_id:
            revenues = revenues.filter(app_id=app_id)
        else:
            revenues = revenues.filter(app__developer=user)
            
        if currency == 'USD':
            # Convert all revenues to USD
            total = sum(revenue.get_amount_usd() for revenue in revenues)
        else:
            # Only sum revenues in specified currency
            total = revenues.filter(currency=currency).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
        return Decimal(str(total))
    
    def get_revenue_metrics(self, app_id):
        """Get detailed revenue metrics for an app"""
        revenues = Revenue.objects.filter(app_id=app_id)
        
        # Basic metrics
        total_revenue = sum(revenue.get_amount_usd() for revenue in revenues)
        monthly_revenue = self.get_monthly_revenue(None, app_id)
        
        # Customer metrics
        total_customers = revenues.aggregate(
            total=Sum('customer_count')
        )['total'] or 0
        
        # Revenue by type
        revenue_by_type = revenues.values('source').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Recurring revenue metrics
        recurring_revenue = revenues.filter(
            is_recurring=True
        ).aggregate(
            total=Sum('amount'),
            avg_amount=Avg('amount')
        )
        
        # Growth metrics
        previous_month = timezone.now().replace(day=1) - timezone.timedelta(days=1)
        previous_month_revenue = revenues.filter(
            created_at__year=previous_month.year,
            created_at__month=previous_month.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        current_month_revenue = monthly_revenue
        mom_growth = 0
        if previous_month_revenue > 0:
            mom_growth = ((current_month_revenue - previous_month_revenue) / previous_month_revenue) * 100
            
        return {
            'total_revenue_usd': total_revenue,
            'monthly_revenue_usd': monthly_revenue,
            'total_customers': total_customers,
            'revenue_by_type': revenue_by_type,
            'recurring_revenue': recurring_revenue,
            'mom_growth': mom_growth,
            'previous_month_revenue': previous_month_revenue,
            'current_month_revenue': current_month_revenue
        }
    
    def create_recurring_revenue(self, parent_revenue):
        """Create a new revenue record for recurring revenue"""
        if not parent_revenue.is_recurring:
            raise ValueError("Parent revenue is not recurring")
            
        # Calculate next period
        if parent_revenue.recurring_interval == 'MONTHLY':
            delta = timezone.timedelta(days=30)
        elif parent_revenue.recurring_interval == 'QUARTERLY':
            delta = timezone.timedelta(days=90)
        elif parent_revenue.recurring_interval == 'ANNUALLY':
            delta = timezone.timedelta(days=365)
        else:
            raise ValueError("Invalid recurring interval")
            
        # Create new revenue record
        new_revenue = Revenue.objects.create(
            app=parent_revenue.app,
            amount=parent_revenue.amount,
            currency=parent_revenue.currency,
            source=parent_revenue.source,
            description=f"Recurring {parent_revenue.recurring_interval.lower()} revenue",
            period_start=parent_revenue.period_end,
            period_end=parent_revenue.period_end + delta,
            is_recurring=True,
            recurring_interval=parent_revenue.recurring_interval,
            parent_revenue=parent_revenue,
            customer_count=parent_revenue.customer_count,
            metadata=parent_revenue.metadata
        )
        
        return new_revenue
    
    def get_pending_distributions(self, user, app_id=None):
        """Get pending distributions amount"""
        revenues = Revenue.objects.filter(is_distributed=False)
        
        if app_id:
            revenues = revenues.filter(app_id=app_id)
        else:
            revenues = revenues.filter(app__developer=user)
            
        total = revenues.aggregate(total=Sum('amount'))['total']
        return total or 0.00
    
    def calculate_share_distribution(self, app, revenue_amount):
        """Calculate how revenue should be distributed among shareholders"""
        # Get all shareholders and their share counts
        share_ownerships = ShareOwnership.objects.filter(app=app)
        total_shares = sum(ownership.shares_owned for ownership in share_ownerships)
        
        if total_shares == 0:
            raise ValidationError("No shares found for distribution")
        
        distributions = []
        for ownership in share_ownerships:
            if ownership.shares_owned > 0:
                # Calculate share percentage using Decimal for precision
                share_percentage = Decimal(str(ownership.shares_owned)) / Decimal(str(total_shares)) * Decimal('100')
                share_percentage = share_percentage.quantize(Decimal('0.01'))  # Round to 2 decimal places
                
                # Calculate distribution amount
                amount = (share_percentage / Decimal('100')) * revenue_amount
                amount = amount.quantize(Decimal('0.01'))  # Round to 2 decimal places
                
                distributions.append({
                    'recipient': ownership.user,
                    'amount': amount,
                    'share_percentage': share_percentage
                })
        
        # Verify total distribution equals revenue amount
        total_distributed = sum(d['amount'] for d in distributions)
        if total_distributed != revenue_amount:
            # Adjust last distribution to account for rounding differences
            if distributions:
                difference = revenue_amount - total_distributed
                distributions[-1]['amount'] += difference
        
        return distributions
    
    @transaction.atomic
    def process_distribution(self, revenue_id):
        """Process the actual distribution of revenue"""
        with transaction.atomic():
            try:
                revenue = Revenue.objects.select_for_update().get(id=revenue_id)
                if revenue.is_distributed:
                    return False
                    
                distributions = self.calculate_share_distribution(revenue.app, revenue.amount)
                for dist in distributions:
                    Distribution.objects.create(
                        revenue=revenue,
                        recipient=dist['recipient'],
                        amount=dist['amount'],
                        share_percentage=dist['share_percentage']
                    )
                
                revenue.is_distributed = True
                revenue.save()
                return True
                
            except Exception as e:
                logger.error(f"Distribution failed: {str(e)}")
                raise

    def _process_single_distribution(self, distribution):
        """Process a single distribution payment"""
        try:
            # Create transaction record
            transaction = Transaction.objects.create(
                user=distribution.recipient,
                app=distribution.revenue.app,
                amount=distribution.amount,
                transaction_type=Transaction.Type.REVENUE
            )
            
            # Update distribution record
            distribution.status = Distribution.Status.COMPLETED
            distribution.distributed_at = timezone.now()
            distribution.transaction_id = str(transaction.id)
            distribution.save()
            
            # Send notification
            self._notify_distribution(distribution)
            
        except Exception as e:
            distribution.status = Distribution.Status.FAILED
            distribution.error_message = str(e)
            distribution.save()
            raise

    def _notify_distribution(self, distribution):
        """Send notification about distribution"""
        from core.models import Notification
        
        Notification.objects.create(
            user=distribution.recipient,
            type=Notification.Type.DIVIDEND,
            title='Revenue Distribution Received',
            message=f'You have received ${distribution.amount} from {distribution.revenue.app.name}',
            link=f'/revenue/{distribution.revenue.app.id}/'
        )

    def retry_failed_distribution(self, distribution_id):
        """Retry a failed distribution"""
        distribution = Distribution.objects.get(id=distribution_id)
        if distribution.status != Distribution.Status.FAILED:
            raise ValidationError("Only failed distributions can be retried")
            
        distribution.status = Distribution.Status.PROCESSING
        distribution.error_message = ''
        distribution.save()
        
        self._process_single_distribution(distribution)
        return True

    def schedule_distributions(self):
        """Schedule pending distributions for processing"""
        pending_revenues = Revenue.objects.filter(
            is_distributed=False,
            period_end__lte=timezone.now()
        )
        
        for revenue in pending_revenues:
            try:
                self.process_distribution(revenue.id)
            except Exception as e:
                # Log error but continue processing others
                print(f"Error processing revenue {revenue.id}: {str(e)}")
                continue

    def get_distribution_history(self, app_id):
        """Get distribution history for an app"""
        return Distribution.objects.filter(
            revenue__app_id=app_id
        ).select_related('recipient', 'revenue')
    
    def get_monthly_revenue_data(self, app_id):
        """Get monthly revenue data for charts"""
        end_date = timezone.now()
        start_date = end_date.replace(day=1) - timezone.timedelta(days=180)  # Last 6 months
        
        revenues = Revenue.objects.filter(
            app_id=app_id,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values('created_at__month').annotate(
            total=Sum('amount')
        ).order_by('created_at__month')
        
        # Format data for Chart.js
        months = []
        amounts = []
        for revenue in revenues:
            month = datetime(2000, revenue['created_at__month'], 1).strftime('%b')
            months.append(month)
            amounts.append(float(revenue['total']))
            
        return {
            'labels': months,
            'data': amounts
        }
    
    def get_distribution_chart_data(self, app_id):
        """Get distribution data for pie chart"""
        latest_distribution = Distribution.objects.filter(
            revenue__app_id=app_id,
            status=Distribution.Status.COMPLETED
        ).order_by('-distributed_at').first()
        
        if not latest_distribution:
            return {
                'labels': ['No Data'],
                'data': [100]
            }
            
        distributions = Distribution.objects.filter(
            revenue=latest_distribution.revenue
        ).values('recipient__username').annotate(
            total=Sum('amount')
        )
        
        return {
            'labels': [d['recipient__username'] for d in distributions],
            'data': [float(d['total']) for d in distributions]
        }

    def get_recent_distributions(self, app, limit=5):
        """Get recent distributions for an app"""
        return Distribution.objects.filter(
            revenue__app=app,
            status=Distribution.Status.COMPLETED
        ).select_related('revenue').order_by('-distributed_at')[:limit] 
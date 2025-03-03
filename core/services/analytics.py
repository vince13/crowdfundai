from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from ..models import Investment, AppListing, Transaction, UserActivity, Subscription, SubscriptionPlan, SubscriptionFeatureUsage, CommunityVote

class AnalyticsService:
    @staticmethod
    def _decimal_to_float(value):
        """Convert Decimal to float for JSON serialization"""
        if isinstance(value, Decimal):
            return float(value)
        return value

    @staticmethod
    def get_investment_trends(days=30):
        """Calculate investment trends over time"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        daily_investments = Investment.objects.filter(
            created_at__range=(start_date, end_date)
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id')
        ).order_by('date')
        
        # Convert dates to ISO format strings and Decimal to float
        formatted_investments = [
            {
                'date': item['date'].isoformat(),
                'total_amount': float(item['total_amount']) if item['total_amount'] else 0,
                'count': item['count']
            }
            for item in daily_investments
        ]
        
        total_invested = Investment.objects.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        average_investment = Investment.objects.aggregate(
            avg=Avg('amount_paid')
        )['avg'] or 0
        
        return {
            'daily_investments': formatted_investments,
            'total_invested': float(total_invested),
            'average_investment': float(average_investment)
        }
    
    @staticmethod
    def get_user_engagement_metrics(days=30):
        """Track user engagement and activity"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return {
            'active_users': UserActivity.objects.filter(
                last_activity__range=(start_date, end_date)
            ).values('user').distinct().count(),
            
            'hourly_activity': UserActivity.objects.filter(
                last_activity__range=(start_date, end_date)
            ).annotate(
                hour=ExtractHour('last_activity')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('-count')[:5],
            
            'recent_activities': UserActivity.objects.filter(
                last_activity__range=(start_date, end_date)
            ).order_by('-last_activity')[:10]
        }
    
    @staticmethod
    def get_app_performance_metrics():
        """Track app performance and success rates"""
        top_apps = AppListing.objects.annotate(
            total_investment=Sum('investment__amount_paid'),
            investor_count=Count('investment__investor', distinct=True)
        ).order_by('-total_investment')[:5]
        
        # Convert Decimal values to float
        top_performing_apps = []
        for app in top_apps:
            app_dict = {
                'id': app.id,
                'name': app.name,
                'category': app.category,
                'total_investment': float(app.total_investment) if app.total_investment else 0,
                'investor_count': app.investor_count
            }
            top_performing_apps.append(app_dict)
        
        category_distribution = AppListing.objects.values(
            'category'
        ).annotate(
            count=Count('id'),
            total_investment=Sum('investment__amount_paid')
        )
        
        # Convert Decimal values to float in category distribution
        formatted_distribution = [
            {
                'category': item['category'],
                'count': item['count'],
                'total_investment': float(item['total_investment']) if item['total_investment'] else 0
            }
            for item in category_distribution
        ]
        
        return {
            'top_performing_apps': top_performing_apps,
            'category_distribution': formatted_distribution,
            'funding_success_rate': {
                'total_apps': AppListing.objects.count(),
                'funded_apps': AppListing.objects.filter(
                    status='FUNDED'
                ).count()
            }
        }
    
    @staticmethod
    def get_portfolio_analytics(user):
        """Get detailed portfolio analytics for a user"""
        investments = Investment.objects.filter(investor=user)
        
        total_invested = investments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        investments_by_category = investments.values(
            'app__category'
        ).annotate(
            total=Sum('amount_paid'),
            count=Count('id')
        )
        
        # Convert Decimal values to float
        formatted_categories = [
            {
                'category': item['app__category'],
                'total': float(item['total']),
                'count': item['count']
            }
            for item in investments_by_category
        ]
        
        monthly_trends = investments.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            amount=Sum('amount_paid')
        ).order_by('month')
        
        # Convert Decimal values to float and format dates
        formatted_trends = [
            {
                'month': item['month'].isoformat(),
                'amount': float(item['amount']) if item['amount'] else 0
            }
            for item in monthly_trends
        ]
        
        total_returns = Transaction.objects.filter(
            user=user,
            transaction_type='REVENUE'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'total_invested': float(total_invested),
            'investments_by_category': formatted_categories,
            'monthly_investment_trend': formatted_trends,
            'roi_metrics': {
                'total_returns': float(total_returns)
            }
        }

class AdvancedAnalyticsService:
    @classmethod
    def get_churn_metrics(cls, period_days=30):
        """Calculate churn metrics for the specified period"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Get total subscribers at start of period
        total_start = Subscription.objects.filter(
            start_date__lte=start_date,
            is_active=True
        ).count()
        
        # Get churned subscribers in period
        churned = Subscription.objects.filter(
            end_date__range=(start_date, end_date)
        ).count()
        
        # Calculate churn rate
        churn_rate = (churned / total_start * 100) if total_start > 0 else 0
        
        return {
            'period_days': period_days,
            'total_subscribers_start': total_start,
            'churned_subscribers': churned,
            'churn_rate': round(churn_rate, 2)
        }
    
    @classmethod
    def get_retention_metrics(cls):
        """Calculate retention metrics by cohort"""
        now = timezone.now()
        cohorts = []
        
        # Analyze last 6 months of cohorts
        for i in range(6):
            month_start = now.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            
            # Get cohort subscribers
            cohort = Subscription.objects.filter(
                start_date__range=(month_start, month_end)
            )
            
            total_subscribers = cohort.count()
            still_active = cohort.filter(is_active=True).count()
            
            retention_rate = (still_active / total_subscribers * 100) if total_subscribers > 0 else 0
            
            cohorts.append({
                'month': month_start.strftime('%B %Y'),
                'total_subscribers': total_subscribers,
                'retained_subscribers': still_active,
                'retention_rate': round(retention_rate, 2)
            })
        
        return cohorts
    
    @classmethod
    def get_customer_lifetime_value(cls):
        """Calculate Customer Lifetime Value (CLV) metrics"""
        subscriptions = Subscription.objects.select_related('tier').all()
        
        # Calculate average subscription duration
        avg_duration = subscriptions.filter(
            end_date__isnull=False
        ).aggregate(
            avg_days=Avg(F('end_date') - F('start_date'))
        )['avg_days']
        
        avg_duration_days = Decimal('0')
        if avg_duration:
            avg_duration_days = Decimal(str(avg_duration.days))
        
        # Calculate metrics by plan
        clv_by_plan = []
        for plan in SubscriptionPlan.objects.all():
            plan_subs = subscriptions.filter(tier=plan.tier)
            
            # Convert all values to Decimal for calculations
            sub_count = Decimal(str(plan_subs.count()))
            total_revenue = sub_count * plan.price
            avg_months = avg_duration_days / Decimal('30')
            avg_revenue = plan.price * avg_months
            
            clv_by_plan.append({
                'plan_name': plan.name,
                'avg_lifetime_months': float(round(avg_months, 1)),
                'avg_revenue': float(round(avg_revenue, 2)),
                'total_revenue': float(total_revenue)
            })
        
        return {
            'avg_customer_lifetime_days': float(avg_duration_days),
            'clv_by_plan': clv_by_plan
        }
    
    @classmethod
    def get_growth_trends(cls, months=6):
        """Calculate growth trends over time"""
        now = timezone.now()
        trends = []
        
        for i in range(months):
            month_start = now.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            
            new_subscribers = Subscription.objects.filter(
                start_date__range=(month_start, month_end)
            ).count()
            
            churned = Subscription.objects.filter(
                end_date__range=(month_start, month_end)
            ).count()
            
            net_growth = new_subscribers - churned
            
            trends.append({
                'month': month_start.strftime('%B %Y'),
                'new_subscribers': new_subscribers,
                'churned_subscribers': churned,
                'net_growth': net_growth
            })
        
        return trends

    @classmethod
    def get_app_analytics(cls, app):
        """Get detailed analytics for a specific app"""
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        from ..models import CommunityVote

        def decimal_to_float(value):
            """Convert Decimal to float for JSON serialization"""
            if isinstance(value, Decimal):
                return float(value)
            return value

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        # Calculate likes and upvotes from CommunityVote
        likes_count = CommunityVote.objects.filter(
            app=app,
            vote_type='LIKE'
        ).count()

        upvotes_count = CommunityVote.objects.filter(
            app=app,
            vote_type='UPVOTE'
        ).count()

        # Get basic metrics
        basic_metrics = {
            'total_views': app.view_count,
            'total_likes': likes_count,
            'total_upvotes': upvotes_count,
            'total_comments': app.comment_count,
        }

        # Get investment metrics
        investments = app.investment_set.all()
        total_invested = decimal_to_float(investments.aggregate(total=Sum('amount_paid'))['total'] or 0)
        avg_investment = decimal_to_float(investments.aggregate(avg=Avg('amount_paid'))['avg'] or 0)
        
        investment_metrics = {
            'total_invested': total_invested,
            'total_investors': investments.values('investor').distinct().count(),
            'avg_investment': avg_investment,
        }

        # Get trend data
        monthly_trends = investments.filter(
            created_at__gte=thirty_days_ago
        ).annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            amount=Sum('amount_paid'),
            count=Count('id')
        ).order_by('day')

        trends = [{
            'date': item['day'].isoformat(),
            'amount': decimal_to_float(item['amount']),
            'count': item['count']
        } for item in monthly_trends]

        # Calculate engagement changes
        last_month_votes = CommunityVote.objects.filter(
            app=app,
            created_at__gte=thirty_days_ago
        ).count()

        last_week_votes = CommunityVote.objects.filter(
            app=app,
            created_at__gte=seven_days_ago
        ).count()
        
        # Calculate growth rates based on votes
        total_votes = likes_count + upvotes_count  # Total engagement
        growth_rates = {
            'engagement': {
                'monthly': (last_month_votes / total_votes * 100) if total_votes > 0 else 0,
                'weekly': (last_week_votes / total_votes * 100) if total_votes > 0 else 0
            }
        }

        # Convert funding goal to float for calculations
        funding_goal = decimal_to_float(app.funding_goal)
        
        return {
            'basic_metrics': basic_metrics,
            'investment_metrics': investment_metrics,
            'trends': trends,
            'growth_rates': growth_rates,
            'funding_progress': {
                'goal': funding_goal,
                'raised': total_invested,
                'percentage': (total_invested / funding_goal * 100) if funding_goal > 0 else 0
            }
        } 
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum, Count, F
from ..models.subscription import Subscription, SubscriptionFeatureUsage, SubscriptionPlan
from ..services.payments import PaymentService
import logging
from django.db import models

logger = logging.getLogger(__name__)

# Constants for usage tracking
RESET_PERIODS = {
    'daily': timedelta(days=1),
    'monthly': timedelta(days=30)
}

WARNING_THRESHOLD = 0.85  # 85% of limit

class SubscriptionService:
    """Service for managing user subscriptions"""
    
    @classmethod
    def create_subscription(cls, user, tier=Subscription.Tier.FREE):
        """Create a new subscription for user"""
        return Subscription.objects.create(
            user=user,
            tier=tier,
            is_active=True,
            start_date=timezone.now()
        )
    
    @classmethod
    def upgrade_subscription(cls, user, new_tier, payment_method=None, payment_reference=None):
        """Upgrade user's subscription to a new tier"""
        # Get or create subscription
        try:
            subscription = user.subscription
        except:
            # Create new subscription if user doesn't have one
            subscription = cls.create_subscription(user)
        
        # Handle payment first if not already paid
        if new_tier != Subscription.Tier.FREE and not payment_reference:
            payment_amount = cls.get_tier_price(new_tier)
            payment_result = PaymentService.create_subscription_payment(
                user=user,
                plan=new_tier,
                amount=payment_amount
            )
            
            if not payment_result.get('success'):
                return {
                    'success': False,
                    'error': payment_result.get('error', 'Payment failed')
                }
        
        # Update subscription
        subscription.tier = new_tier
        subscription.is_active = True
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=30)
        subscription.last_payment_date = timezone.now()
        subscription.next_payment_date = timezone.now() + timedelta(days=30)
        subscription.payment_method = payment_method
        subscription.save()
        
        return {
            'success': True,
            'subscription': subscription
        }
    
    @classmethod
    def cancel_subscription(cls, user):
        """Cancel user's subscription but maintain access until billing cycle ends"""
        try:
            subscription = user.subscription
            if not subscription:
                return {
                    'success': False,
                    'error': 'No subscription found'
                }
            
            if subscription.tier == Subscription.Tier.FREE:
                return {
                    'success': False,
                    'error': 'Cannot cancel a free subscription'
                }
            
            # Keep the current tier and active status until end date
            subscription.auto_renew = False
            
            # If no end date is set, set it to 30 days from now
            if not subscription.end_date:
                subscription.end_date = timezone.now() + timedelta(days=30)
            
            subscription.save()
            
            return {
                'success': True,
                'message': f'Subscription will be cancelled on {subscription.end_date.strftime("%B %d, %Y")}. You will continue to have access to premium features until then.'
            }
        except Exception as e:
            logger.exception("Error in cancel_subscription service")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def get_tier_price(cls, tier):
        """Get price for subscription tier"""
        try:
            plan = SubscriptionPlan.objects.get(tier=tier, is_active=True)
            return plan.price
        except SubscriptionPlan.DoesNotExist:
            return 0
    
    @classmethod
    def get_tier_features(cls, tier):
        """Get list of features for a subscription tier"""
        try:
            plan = SubscriptionPlan.objects.get(tier=tier, is_active=True)
            return {
                'name': plan.name,
                'price': plan.price,
                'features': plan.features
            }
        except SubscriptionPlan.DoesNotExist:
            # Fallback to default free plan
            return {
                'name': 'Free',
                'price': 0,
                'features': [
                    'Basic app listing',
                    'Basic portfolio management',
                    'Standard transaction processing',
                    'Basic AI insights'
                ]
            }
    
    @classmethod
    def check_subscription_status(cls):
        """Check and update status of all subscriptions"""
        now = timezone.now()
        
        # Find expired subscriptions
        expired = Subscription.objects.filter(
            is_active=True,
            end_date__lt=now
        )
        
        for subscription in expired:
            if subscription.auto_renew:
                # Attempt to renew
                payment_result = PaymentService.create_subscription_payment(
                    user=subscription.user,
                    plan=subscription.tier,
                    amount=cls.get_tier_price(subscription.tier)
                )
                
                if payment_result.get('success'):
                    subscription.end_date = now + timedelta(days=30)
                    subscription.last_payment_date = now
                    subscription.next_payment_date = now + timedelta(days=30)
                    subscription.save()
                else:
                    subscription.is_active = False
                    subscription.save()
            else:
                subscription.is_active = False
                subscription.save()
    
    @classmethod
    def get_plan_metrics(cls, plan_id=None):
        """Get metrics for a specific plan or all plans"""
        try:
            if plan_id:
                plans = SubscriptionPlan.objects.filter(id=plan_id)
            else:
                plans = SubscriptionPlan.objects.all()
            
            metrics = []
            for plan in plans:
                subscriptions = Subscription.objects.filter(tier=plan.tier)
                active_subscriptions = subscriptions.filter(is_active=True)
                
                metric = {
                    'plan_name': plan.name,
                    'plan_tier': plan.tier,
                    'total_subscribers': subscriptions.count(),
                    'active_subscribers': active_subscriptions.count(),
                    'monthly_revenue': active_subscriptions.count() * plan.price,
                    'total_revenue': subscriptions.count() * plan.price,  # Historical total
                    'is_active': plan.is_active
                }
                metrics.append(metric)
            
            return {
                'success': True,
                'metrics': metrics
            }
        except Exception as e:
            logger.exception("Error getting plan metrics")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def get_subscription_revenue(cls, start_date=None, end_date=None):
        """Get subscription revenue for a date range"""
        try:
            subscriptions = Subscription.objects.exclude(tier=Subscription.Tier.FREE)
            
            if start_date:
                subscriptions = subscriptions.filter(start_date__gte=start_date)
            if end_date:
                subscriptions = subscriptions.filter(start_date__lte=end_date)
            
            revenue_by_tier = {}
            for tier_choice in Subscription.Tier.choices:
                tier = tier_choice[0]
                tier_subscriptions = subscriptions.filter(tier=tier)
                try:
                    plan = SubscriptionPlan.objects.get(tier=tier, is_active=True)
                    revenue = tier_subscriptions.count() * plan.price
                except SubscriptionPlan.DoesNotExist:
                    revenue = 0
                
                revenue_by_tier[tier] = {
                    'count': tier_subscriptions.count(),
                    'revenue': revenue
                }
            
            return {
                'success': True,
                'revenue_by_tier': revenue_by_tier,
                'total_revenue': sum(tier['revenue'] for tier in revenue_by_tier.values())
            }
        except Exception as e:
            logger.exception("Error getting subscription revenue")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def track_feature_usage(cls, user, feature_name):
        """Track usage of a subscription feature"""
        try:
            subscription = Subscription.objects.get(user=user, is_active=True)
            feature_usage, created = SubscriptionFeatureUsage.objects.get_or_create(
                subscription=subscription,
                feature_name=feature_name
            )
            
            # Check if usage is allowed
            if not feature_usage.check_usage_allowed():
                return {
                    'success': False,
                    'error': 'Usage limit exceeded',
                    'usage_stats': feature_usage.get_usage_stats()
                }
            
            # Increment usage
            feature_usage.increment_usage()
            
            # Check for warning threshold
            limits = feature_usage.get_usage_limits()
            daily_ratio = feature_usage.daily_usage / limits['daily_limit']
            monthly_ratio = feature_usage.monthly_usage / limits['monthly_limit']
            
            result = {
                'success': True,
                'usage_stats': feature_usage.get_usage_stats()
            }
            
            if daily_ratio >= WARNING_THRESHOLD or monthly_ratio >= WARNING_THRESHOLD:
                result['warning'] = {
                    'approaching_limit': True,
                    'daily_ratio': daily_ratio,
                    'monthly_ratio': monthly_ratio
                }
            
            return result
            
        except Subscription.DoesNotExist:
            return {
                'success': False,
                'error': 'No active subscription found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def get_feature_usage_analytics(cls, user, days=30):
        """Get analytics for feature usage"""
        try:
            subscription = Subscription.objects.get(user=user, is_active=True)
            feature_usages = SubscriptionFeatureUsage.objects.filter(subscription=subscription)
            
            now = timezone.now()
            start_date = now - timedelta(days=days)
            
            daily_trends = []
            feature_breakdown = []
            current_status = []
            
            for usage in feature_usages:
                # Get daily trends
                daily_trends.append({
                    'feature_name': usage.feature_name,
                    'day': now.date(),
                    'total_usage': usage.daily_usage,
                    'avg_usage': usage.monthly_usage / 30.0
                })
                
                # Get feature breakdown
                feature_breakdown.append({
                    'feature_name': usage.feature_name,
                    'total_usage': usage.monthly_usage,
                    'daily_avg': usage.daily_usage,
                    'monthly_avg': usage.monthly_usage / 30.0
                })
                
                # Get current status
                limits = usage.get_usage_limits()
                current_status.append({
                    'feature': usage.feature_name,
                    'current_usage': usage.get_usage_stats(),
                    'limits': {
                        'daily': limits['daily_limit'],
                        'monthly': limits['monthly_limit']
                    },
                    'utilization': {
                        'daily': usage.daily_usage / limits['daily_limit'],
                        'monthly': usage.monthly_usage / limits['monthly_limit']
                    }
                })
            
            return {
                'success': True,
                'daily_trends': daily_trends,
                'feature_breakdown': feature_breakdown,
                'current_status': current_status,
                'current_usage': current_status[0] if current_status else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def reset_usage_counters(cls):
        """Reset usage counters based on reset periods"""
        try:
            now = timezone.now()
            reset_count = 0
            
            for usage in SubscriptionFeatureUsage.objects.all():
                daily_reset = now - usage.daily_reset_at >= RESET_PERIODS['daily']
                monthly_reset = now - usage.monthly_reset_at >= RESET_PERIODS['monthly']
                
                if daily_reset:
                    usage.daily_usage = 0
                    usage.daily_reset_at = now
                    reset_count += 1
                
                if monthly_reset:
                    usage.monthly_usage = 0
                    usage.monthly_reset_at = now
                    reset_count += 1
                
                if daily_reset or monthly_reset:
                    usage.save(update_fields=['daily_usage', 'monthly_usage', 'daily_reset_at', 'monthly_reset_at'])
            
            # Force refresh all feature usage objects
            SubscriptionFeatureUsage.objects.all().update(
                daily_usage=models.F('daily_usage'),
                monthly_usage=models.F('monthly_usage')
            )
            
            return {
                'success': True,
                'reset_count': reset_count
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            } 
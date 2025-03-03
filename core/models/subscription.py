from django.db import models
from django.utils import timezone
from .base import User
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

# Constants for usage tracking
RESET_PERIODS = {
    'daily': timedelta(days=1),
    'monthly': timedelta(days=30)
}

WARNING_THRESHOLD = 0.85  # 85% of limit

class Subscription(models.Model):
    class Tier(models.TextChoices):
        FREE = 'FREE', 'Free'
        DEV_PRO = 'DEV_PRO', 'Developer Pro'
        INV_PRO = 'INV_PRO', 'Investor Pro'
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.FREE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    
    # Payment tracking
    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    
    # Feature flags for granular control
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['tier', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.tier}"
    
    def is_pro(self):
        return self.tier in [self.Tier.DEV_PRO, self.Tier.INV_PRO]
    
    def has_feature(self, feature_name):
        """Check if subscription tier has access to a specific feature"""
        feature_matrix = {
            self.Tier.FREE: [
                'basic_ai_insights',
                'basic_portfolio',
                'standard_transactions',
            ],
            self.Tier.DEV_PRO: [
                'advanced_ai_assessment',
                'market_analysis',
                'tech_evaluation',
                'priority_listing',
                'api_access',
                'custom_branding',
                'priority_support',
                'marketing_tools',
            ],
            self.Tier.INV_PRO: [
                'detailed_risk_analysis',
                'portfolio_optimization',
                'market_trends',
                'investment_alerts',
                'due_diligence_tools',
                'early_access',
                'priority_processing',
                'exclusive_events',
            ]
        }
        
        tier_features = feature_matrix.get(self.tier, [])
        if self.tier != self.Tier.FREE:
            # Pro tiers include all free features
            tier_features.extend(feature_matrix[self.Tier.FREE])
        
        return feature_name in tier_features

class SubscriptionFeatureUsage(models.Model):
    """Track usage of subscription features"""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='feature_usage')
    feature_name = models.CharField(max_length=100)
    usage_count = models.IntegerField(default=0, null=True)
    daily_usage = models.IntegerField(default=0)
    monthly_usage = models.IntegerField(default=0)
    daily_reset_at = models.DateTimeField(auto_now_add=True)
    monthly_reset_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('subscription', 'feature_name')
        indexes = [
            models.Index(fields=['daily_reset_at']),
            models.Index(fields=['monthly_reset_at']),
        ]
    
    def __str__(self):
        return f"{self.subscription.user.email} - {self.feature_name}"

    def increment_usage(self):
        """Increment usage counters"""
        self.daily_usage += 1
        self.monthly_usage += 1
        self.save()
    
    def get_usage_limits(self):
        """Get the usage limits for this feature based on subscription tier"""
        tier_limits = {
            'FREE': {'daily': 100, 'monthly': 1000},
            'DEV_PRO': {'daily': 1000, 'monthly': 10000},
            'INV_PRO': {'daily': 5000, 'monthly': 50000}
        }
        
        tier = self.subscription.tier
        limits = tier_limits.get(tier, tier_limits['FREE'])
        
        return {
            'daily_limit': limits['daily'],
            'monthly_limit': limits['monthly']
        }
    
    def check_usage_allowed(self):
        """Check if the feature can be used based on current usage and limits"""
        limits = self.get_usage_limits()
        return self.daily_usage < limits['daily_limit'] and self.monthly_usage < limits['monthly_limit']
    
    def get_usage_stats(self):
        """Get current usage statistics for this feature"""
        limits = self.get_usage_limits()
        return {
            'daily_usage': self.daily_usage,
            'monthly_usage': self.monthly_usage,
            'daily_limit': limits['daily_limit'],
            'monthly_limit': limits['monthly_limit'],
            'daily_reset_at': self.daily_reset_at,
            'monthly_reset_at': self.monthly_reset_at
        }

class SubscriptionPlan(models.Model):
    """Model for managing subscription plans and pricing"""
    tier = models.CharField(max_length=10, choices=Subscription.Tier.choices, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    features = models.JSONField(default=list)  # Store features as a JSON array
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} (₦{self.price})" 
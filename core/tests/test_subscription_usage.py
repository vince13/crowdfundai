from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from core.models.subscription import Subscription, SubscriptionFeatureUsage
from core.services.subscription import SubscriptionService
from core.tests import create_test_user

class SubscriptionUsageTrackingTests(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.subscription = Subscription.objects.create(
            user=self.user,
            tier=Subscription.Tier.DEV_PRO,
            is_active=True
        )
        self.feature_usage = SubscriptionFeatureUsage.objects.create(
            subscription=self.subscription,
            feature_name='api_access',
            daily_usage=0,
            monthly_usage=0
        )
        self.subscription_service = SubscriptionService()

    def test_reset_usage_counters(self):
        """Test resetting usage counters"""
        # Set some initial usage and old reset times
        self.feature_usage.daily_usage = 10
        self.feature_usage.monthly_usage = 50
        self.feature_usage.daily_reset_at = timezone.now() - timedelta(days=2)  # Force daily reset
        self.feature_usage.monthly_reset_at = timezone.now() - timedelta(days=31)  # Force monthly reset
        self.feature_usage.save()

        # Reset counters
        result = self.subscription_service.reset_usage_counters()
        self.assertTrue(result['success'])
        self.assertIn('reset_count', result)

        # Verify counters are reset
        self.feature_usage.refresh_from_db()
        self.assertEqual(self.feature_usage.daily_usage, 0)
        self.assertEqual(self.feature_usage.monthly_usage, 0)

    def test_increment_usage(self):
        """Test incrementing feature usage"""
        # Test daily usage increment
        self.feature_usage.increment_usage()
        self.assertEqual(self.feature_usage.daily_usage, 1)
        self.assertEqual(self.feature_usage.monthly_usage, 1)

        # Test multiple increments
        self.feature_usage.increment_usage()
        self.feature_usage.increment_usage()
        self.assertEqual(self.feature_usage.daily_usage, 3)
        self.assertEqual(self.feature_usage.monthly_usage, 3)

    def test_get_usage_limits(self):
        """Test retrieving usage limits for features"""
        limits = self.feature_usage.get_usage_limits()
        self.assertIn('daily_limit', limits)
        self.assertIn('monthly_limit', limits)
        self.assertTrue(isinstance(limits['daily_limit'], int))
        self.assertTrue(isinstance(limits['monthly_limit'], int))

    def test_check_usage_allowed(self):
        """Test checking if feature usage is allowed"""
        # Should be allowed when usage is below limits
        self.assertTrue(self.feature_usage.check_usage_allowed())

        # Set usage near limit
        self.feature_usage.daily_usage = 999999
        self.feature_usage.save()
        self.assertFalse(self.feature_usage.check_usage_allowed())

    def test_get_usage_stats(self):
        """Test retrieving usage statistics"""
        stats = self.feature_usage.get_usage_stats()
        self.assertIn('daily_usage', stats)
        self.assertIn('monthly_usage', stats)
        self.assertIn('daily_limit', stats)
        self.assertIn('monthly_limit', stats)
        self.assertIn('daily_reset_at', stats)
        self.assertIn('monthly_reset_at', stats)

    def test_track_feature_usage(self):
        """Test tracking feature usage through SubscriptionService"""
        result = self.subscription_service.track_feature_usage(
            user=self.user,
            feature_name='api_access'
        )
        self.assertTrue(result['success'])
        self.assertIn('usage_stats', result)
        self.assertTrue(isinstance(result['usage_stats'], dict))

    def test_get_feature_usage_analytics(self):
        """Test retrieving feature usage analytics"""
        analytics = self.subscription_service.get_feature_usage_analytics(
            user=self.user,
            days=30
        )
        self.assertIn('daily_trends', analytics)
        self.assertIn('feature_breakdown', analytics)
        self.assertIn('current_usage', analytics)

    def test_usage_limit_warning(self):
        """Test usage limit warning threshold"""
        # Set usage near warning threshold
        self.feature_usage.daily_usage = 85  # Assuming 100 is the daily limit
        self.feature_usage.save()

        result = self.subscription_service.track_feature_usage(
            user=self.user,
            feature_name='api_access'
        )
        self.assertTrue(result['success'])
        self.assertTrue(result.get('warning'))
        self.assertIn('approaching_limit', result['warning']) 
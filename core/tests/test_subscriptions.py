from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from unittest.mock import patch, MagicMock
from core.models.subscription import Subscription, SubscriptionFeatureUsage
from core.services.subscription import SubscriptionService
from core.services.payments import PaymentService
from core.tests import create_test_user

User = get_user_model()

class SubscriptionModelTests(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.subscription = Subscription.objects.create(
            user=self.user,
            tier=Subscription.Tier.FREE,
            is_active=True,
            start_date=timezone.now()
        )

    def test_subscription_creation(self):
        """Test creating a subscription"""
        self.assertEqual(self.subscription.user, self.user)
        self.assertEqual(self.subscription.tier, Subscription.Tier.FREE)
        self.assertTrue(self.subscription.is_active)
        self.assertIsNone(self.subscription.end_date)

    def test_subscription_str_representation(self):
        """Test the string representation of subscription"""
        expected_str = f"{self.user.email} - {Subscription.Tier.FREE}"
        self.assertEqual(str(self.subscription), expected_str)

    def test_is_pro_method(self):
        """Test is_pro method for different tiers"""
        self.assertFalse(self.subscription.is_pro())
        
        self.subscription.tier = Subscription.Tier.DEV_PRO
        self.subscription.save()
        self.assertTrue(self.subscription.is_pro())
        
        self.subscription.tier = Subscription.Tier.INV_PRO
        self.subscription.save()
        self.assertTrue(self.subscription.is_pro())

    def test_has_feature_method(self):
        """Test feature access for different subscription tiers"""
        # Test FREE tier features
        self.assertTrue(self.subscription.has_feature('basic_ai_insights'))
        self.assertTrue(self.subscription.has_feature('basic_portfolio'))
        self.assertFalse(self.subscription.has_feature('advanced_ai_assessment'))

        # Test DEV_PRO tier features
        self.subscription.tier = Subscription.Tier.DEV_PRO
        self.subscription.save()
        self.assertTrue(self.subscription.has_feature('advanced_ai_assessment'))
        self.assertTrue(self.subscription.has_feature('api_access'))
        self.assertTrue(self.subscription.has_feature('basic_ai_insights'))  # Should include FREE features
        self.assertFalse(self.subscription.has_feature('due_diligence_tools'))

        # Test INV_PRO tier features
        self.subscription.tier = Subscription.Tier.INV_PRO
        self.subscription.save()
        self.assertTrue(self.subscription.has_feature('due_diligence_tools'))
        self.assertTrue(self.subscription.has_feature('basic_ai_insights'))  # Should include FREE features
        self.assertFalse(self.subscription.has_feature('api_access'))

class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = create_test_user()

    def test_create_subscription(self):
        """Test creating a new subscription"""
        subscription = SubscriptionService.create_subscription(self.user)
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.tier, Subscription.Tier.FREE)
        self.assertTrue(subscription.is_active)

    @patch('core.services.payments.PaymentService.create_subscription_payment')
    def test_upgrade_subscription_success(self, mock_payment):
        """Test successful subscription upgrade"""
        mock_payment.return_value = {'success': True}
        
        # Test upgrade with new payment
        result = SubscriptionService.upgrade_subscription(
            user=self.user,
            new_tier=Subscription.Tier.DEV_PRO,
            payment_method='paystack'
        )
        self.assertTrue(result['success'])
        
        # Test upgrade with existing payment reference
        result = SubscriptionService.upgrade_subscription(
            user=self.user,
            new_tier=Subscription.Tier.DEV_PRO,
            payment_method='paystack',
            payment_reference='sub_test123'
        )
        self.assertTrue(result['success'])
        
        subscription = result['subscription']
        self.assertEqual(subscription.tier, Subscription.Tier.DEV_PRO)
        self.assertTrue(subscription.is_active)
        self.assertIsNotNone(subscription.end_date)
        self.assertEqual(subscription.payment_method, 'paystack')

    @patch('core.services.payments.PaymentService.create_subscription_payment')
    def test_upgrade_subscription_payment_failure(self, mock_payment):
        """Test subscription upgrade with payment failure"""
        mock_payment.return_value = {
            'success': False,
            'error': 'Payment failed'
        }
        
        result = SubscriptionService.upgrade_subscription(
            user=self.user,
            new_tier=Subscription.Tier.DEV_PRO,
            payment_method='paystack'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Payment failed')

    def test_cancel_subscription(self):
        """Test cancelling a subscription"""
        subscription = SubscriptionService.create_subscription(self.user)
        subscription.next_payment_date = timezone.now() + timedelta(days=30)
        subscription.save()
        
        result = SubscriptionService.cancel_subscription(self.user)
        
        self.assertTrue(result['success'])
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)
        self.assertFalse(subscription.auto_renew)
        self.assertEqual(subscription.end_date, subscription.next_payment_date)

    def test_get_tier_price(self):
        """Test getting prices for different tiers"""
        self.assertEqual(SubscriptionService.get_tier_price(Subscription.Tier.FREE), 0)
        self.assertEqual(SubscriptionService.get_tier_price(Subscription.Tier.DEV_PRO), 99.99)
        self.assertEqual(SubscriptionService.get_tier_price(Subscription.Tier.INV_PRO), 149.99)

    def test_get_tier_features(self):
        """Test getting features for different tiers"""
        free_features = SubscriptionService.get_tier_features(Subscription.Tier.FREE)
        self.assertEqual(free_features['name'], 'Free')
        self.assertEqual(free_features['price'], 0)
        self.assertTrue(isinstance(free_features['features'], list))
        
        dev_features = SubscriptionService.get_tier_features(Subscription.Tier.DEV_PRO)
        self.assertEqual(dev_features['name'], 'Developer Pro')
        self.assertEqual(dev_features['price'], 99.99)
        self.assertTrue('API access' in dev_features['features'])

class SubscriptionFeatureUsageTests(TestCase):
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
            usage_count=0
        )

    def test_feature_usage_creation(self):
        """Test creating a feature usage record"""
        self.assertEqual(self.feature_usage.subscription, self.subscription)
        self.assertEqual(self.feature_usage.feature_name, 'api_access')
        self.assertEqual(self.feature_usage.usage_count, 0)
        self.assertIsNotNone(self.feature_usage.last_used)

    def test_feature_usage_str_representation(self):
        """Test the string representation of feature usage"""
        expected_str = f"{self.user.email} - api_access"
        self.assertEqual(str(self.feature_usage), expected_str)

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

    def test_reset_usage_counters(self):
        """Test resetting usage counters"""
        # Set some initial usage
        self.feature_usage.daily_usage = 10
        self.feature_usage.monthly_usage = 50
        self.feature_usage.save()

        # Reset counters
        result = self.subscription_service.reset_usage_counters()
        self.assertTrue(result['success'])
        self.assertIn('reset_count', result)

        # Verify counters are reset
        self.feature_usage.refresh_from_db()
        self.assertEqual(self.feature_usage.daily_usage, 0)
        self.assertEqual(self.feature_usage.monthly_usage, 0)

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

class PaymentIntegrationTests(TestCase):
    def setUp(self):
        self.user = create_test_user()

    @patch('core.services.payments.PaymentService.create_subscription_payment')
    def test_create_subscription_payment(self, mock_create_payment):
        """Test creating a subscription payment"""
        mock_create_payment.return_value = {
            'success': True,
            'authorization_url': 'https://checkout.paystack.com/test',
            'access_code': 'test_code',
            'reference': 'sub_test123'
        }
        
        result = PaymentService.create_subscription_payment(
            user=self.user,
            plan=Subscription.Tier.DEV_PRO,
            amount=99.99
        )
        
        self.assertTrue(result['success'])
        self.assertIn('authorization_url', result)
        self.assertIn('reference', result)

    @patch('core.services.payments.PaymentService.verify_subscription_payment')
    def test_verify_subscription_payment(self, mock_verify_payment):
        """Test verifying a subscription payment"""
        mock_verify_payment.return_value = {
            'success': True,
            'amount': 9999,
            'currency': 'NGN',
            'plan': Subscription.Tier.DEV_PRO,
            'user_id': str(self.user.id)
        }
        
        result = PaymentService.verify_subscription_payment('sub_test123')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['plan'], Subscription.Tier.DEV_PRO)
        self.assertEqual(result['user_id'], str(self.user.id)) 

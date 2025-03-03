from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import NotificationPreference
from decimal import Decimal

User = get_user_model()

class NotificationPreferenceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.preferences_url = reverse('core:notification_preferences')
        
    def test_notification_preference_creation(self):
        """Test that notification preferences are created with correct defaults"""
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_notifications)
        self.assertTrue(prefs.push_notifications)
        self.assertTrue(prefs.price_alerts)
        self.assertTrue(prefs.app_approval_notifications)
        
    def test_notification_preference_update(self):
        """Test updating notification preferences"""
        # Initial state check
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.price_alerts)
        self.assertTrue(prefs.app_approval_notifications)
        
        # Update preferences through POST request
        data = {
            'email_notifications': 'on',
            'push_notifications': 'on',
            'price_alerts': 'on',
            'app_approval_notifications': 'on',
            'investment_notifications': 'on',
            'system_notifications': 'on',
            'milestone_notifications': 'on',
            'app_update_notifications': 'on',
            'funding_goal_notifications': 'on',
            'dividend_notifications': 'on',
            'security_notifications': 'on',
            'maintenance_notifications': 'on',
            'news_notifications': 'on',
            'price_alert_threshold': '5.00'
        }
        
        response = self.client.post(self.preferences_url, data)
        self.assertEqual(response.status_code, 302)  # Should redirect after successful update
        
        # Verify preferences were updated
        prefs.refresh_from_db()
        self.assertTrue(prefs.price_alerts)
        self.assertTrue(prefs.app_approval_notifications)
        
        # Test disabling preferences
        data.pop('price_alerts')  # Remove to simulate unchecked
        data.pop('app_approval_notifications')  # Remove to simulate unchecked
        
        response = self.client.post(self.preferences_url, data)
        self.assertEqual(response.status_code, 302)
        
        # Verify preferences were disabled
        prefs.refresh_from_db()
        self.assertFalse(prefs.price_alerts)
        self.assertFalse(prefs.app_approval_notifications)
        
    def test_form_data_processing(self):
        """Test that form data is being processed correctly"""
        # Make a POST request and capture the request data
        data = {
            'email_notifications': 'on',
            'push_notifications': 'on',
            'price_alerts': 'on',
            'app_approval_notifications': 'on',
            'price_alert_threshold': '5.00'
        }
        
        response = self.client.post(self.preferences_url, data, follow=True)
        
        # Print debug information in the test output
        prefs = NotificationPreference.objects.get(user=self.user)
        print(f"\nPOST Data: {data}")
        print(f"Resulting Preferences:")
        print(f"- price_alerts: {prefs.price_alerts}")
        print(f"- app_approval_notifications: {prefs.app_approval_notifications}")
        
        self.assertTrue(prefs.price_alerts)
        self.assertTrue(prefs.app_approval_notifications) 
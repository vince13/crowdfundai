from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.conf import settings
from decimal import Decimal
from core.models import AppListing, User, Notification
from core.services.notifications import NotificationService
import logging
from datetime import timedelta
from django.utils import timezone

class PlatformFeeNotificationTests(TestCase):
    def setUp(self):
        # Create a developer user
        self.developer = User.objects.create_user(
            username='developer',  # Add username field
            email='developer@test.com',
            password='testpass123',
            role='DEVELOPER'  # Use string instead of User.Role.DEVELOPER
        )
        
        # Create an admin user
        self.admin = User.objects.create_user(
            username='admin',  # Add username field
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            role='ADMIN'  # Use string instead of User.Role.ADMIN
        )
        
        # Create a test app
        self.app = AppListing.objects.create(
            name='Test App',
            developer=self.developer,
            funding_goal=Decimal('1000000.00'),
            status='FUNDED',  # Use string instead of AppListing.Status.FUNDED
            exchange_rate=Decimal('1.00'),  # Add required exchange_rate field
            currency='USD',  # Add required currency field
            available_percentage=Decimal('100.00'),
            equity_percentage=Decimal('10.00'),
            funding_end_date=timezone.now() + timedelta(days=30)  # Add required funding_end_date field
        )

    def test_successful_funding_notification(self):
        """Test notification when funding completes successfully"""
        # Clear any existing emails
        mail.outbox = []
        
        # Test amounts
        total_amount = Decimal('1000000.00')
        platform_fee = Decimal('50000.00')  # 5% of total
        
        # Send notification
        notification = NotificationService.notify_developer_funding_complete(
            app=self.app,
            amount=total_amount,
            platform_fee=platform_fee
        )
        
        # Check in-app notification was created
        self.assertTrue(
            Notification.objects.filter(
                user=self.developer,
                type='FUNDING_COMPLETE',  # Use string instead of Notification.Type.FUNDING_COMPLETE
                title=f"Funding Complete - {self.app.name}"
            ).exists()
        )
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        # Verify email recipients
        self.assertEqual(email.to, [self.developer.email])
        
        # Verify email subject
        self.assertEqual(email.subject, f"Funding Complete - {self.app.name}")
        
        # Verify email content
        html_content = email.alternatives[0][0] if email.alternatives else ''
        self.assertIn(str(total_amount), html_content)
        self.assertIn(str(platform_fee), html_content)
        self.assertIn(str(total_amount - platform_fee), html_content)
        self.assertIn(self.app.name, html_content)
        
        # Verify email contains the app URL
        app_url = reverse('core:app_detail', kwargs={'pk': self.app.id})
        self.assertIn(app_url, html_content)

    def test_fee_processing_failed_notification(self):
        """Test notification when platform fee processing fails"""
        # Clear any existing emails
        mail.outbox = []
        
        # Test error message
        error_message = "Payment gateway timeout"
        
        # Send notification
        NotificationService.notify_admins_fee_processing_failed(
            app=self.app,
            error=error_message
        )
        
        # Check in-app notification was created
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin,
                type='SYSTEM_ERROR',  # Use string instead of Notification.Type.SYSTEM_ERROR
                title=f"Platform Fee Processing Failed - {self.app.name}",
                severity='HIGH'  # Use string instead of Notification.Severity.HIGH
            ).exists()
        )
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        html_content = email.alternatives[0][0] if email.alternatives else ''
        
        # Verify email recipients
        self.assertEqual(email.to, [self.admin.email])
        
        # Verify email subject
        self.assertEqual(
            email.subject,
            f"Platform Fee Processing Failed - {self.app.name}"
        )
        
        # Verify email content
        self.assertIn(self.app.name, html_content)
        self.assertIn(str(self.app.id), html_content)
        self.assertIn(error_message, html_content)
        self.assertIn(f"₦{float(self.app.funding_goal):.2f}", html_content)
        self.assertIn(f"₦{float(self.app.calculate_platform_fee()):.2f}", html_content)
        
        # Verify email contains the dashboard URL
        self.assertIn('/platform-fees/', html_content)

    def test_multiple_admins_notification(self):
        """Test that all admins receive notifications when fee processing fails"""
        # Create additional admin users
        admin2 = User.objects.create_user(
            username='admin2',  # Add username field
            email='admin2@test.com',
            password='testpass123',
            is_staff=True,
            role='ADMIN'  # Use string instead of User.Role.ADMIN
        )
        admin3 = User.objects.create_user(
            username='admin3',  # Add username field
            email='admin3@test.com',
            password='testpass123',
            is_staff=True,
            role='ADMIN'  # Use string instead of User.Role.ADMIN
        )
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        NotificationService.notify_admins_fee_processing_failed(
            app=self.app,
            error="Test error"
        )
        
        # Check that all admins received notifications
        admin_emails = [self.admin.email, admin2.email, admin3.email]
        
        # Verify in-app notifications
        for admin in admin_emails:
            self.assertTrue(
                Notification.objects.filter(
                    user__email=admin,
                    type='SYSTEM_ERROR'  # Use string instead of Notification.Type.SYSTEM_ERROR
                ).exists()
            )
        
        # Verify emails
        self.assertEqual(len(mail.outbox), 3)  # One email per admin
        received_emails = [email.to[0] for email in mail.outbox]
        for admin_email in admin_emails:
            self.assertIn(admin_email, received_emails)

    def test_notification_error_handling(self):
        """Test error handling when notification sending fails"""
        # Clear any existing emails
        mail.outbox = []
        
        # Create a test app with valid data
        test_app = AppListing.objects.create(
            name='Test App 2',
            developer=self.developer,
            funding_goal=Decimal('1000000.00'),
            status='LISTED',
            exchange_rate=Decimal('1.00'),
            currency='NGN',
            equity_percentage=Decimal('1.00'),
            available_percentage=Decimal('0.00'),
            funding_end_date=timezone.now() + timedelta(days=180),
            price_per_percentage=Decimal('10000.00')
        )
        
        # Save original method
        original_send_email = NotificationService.send_email_notification
        
        # Mock send_email_notification to raise an error
        def mock_send_email(*args, **kwargs):
            raise Exception("Test error")
        
        try:
            # Replace send_email_notification with our mock
            NotificationService.send_email_notification = staticmethod(mock_send_email)
            
            # Attempt to send notification
            NotificationService.notify_admins_fee_processing_failed(
                app=test_app,
                error="Test error"
            )
            
            # Verify that no emails were sent (due to error)
            self.assertEqual(len(mail.outbox), 0)
            
            # But the notification was still created
            self.assertTrue(
                Notification.objects.filter(
                    user=self.admin,
                    type='SYSTEM_ERROR',
                    title=f"Platform Fee Processing Failed - {test_app.name}"
                ).exists()
            )
        finally:
            # Restore original method
            NotificationService.send_email_notification = original_send_email 
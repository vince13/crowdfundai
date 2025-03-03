import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import (
    AppListing,
    Investment,
    EscrowTransaction,
    ShareOwnership,
    ProjectMilestone
)
from ..services.payments import PaymentService
from ..services.escrow import EscrowService
import json
from datetime import timedelta

User = get_user_model()

class TestPaymentEdgeCases(TestCase):
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create test users
        self.investor = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='testpass123',
            role=User.Role.INVESTOR
        )
        
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@example.com',
            password='testpass123',
            role=User.Role.DEVELOPER
        )
        
        # Create test app listing
        self.app_listing = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            developer=self.developer,
            funding_goal=Decimal('10000.00'),
            currency='NGN',
            exchange_rate=Decimal('1.0000'),
            available_percentage=Decimal('20.00'),
            min_investment_percentage=Decimal('5.00'),
            equity_percentage=Decimal('20.00'),
            price_per_percentage=Decimal('500.00'),
            remaining_percentage=Decimal('20.00'),
            funding_end_date=timezone.now() + timedelta(days=30)
        )
        
        self.client.force_login(self.investor)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_concurrent_payments(self, mock_create):
        """Test handling of concurrent payments for the same investment"""
        mock_create.return_value = {'success': True, 'data': {'reference': 'test_ref'}}
        
        investment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'app_id': self.app_listing.id,
            'shares': '10'
        }
        
        # Make first payment request
        response1 = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        self.assertEqual(response1.status_code, 200)
        
        # Make second payment request immediately
        response2 = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        self.assertEqual(response2.status_code, 400)
        
        # Verify only one investment was created
        self.assertEqual(Investment.objects.count(), 1)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_partial_payment_completion(self, mock_create):
        """Test handling of partial payment completion"""
        mock_create.return_value = {'success': True, 'data': {'reference': 'test_ref'}}
        
        investment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'app_id': self.app_listing.id,
            'shares': '10'
        }
        
        response = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        self.assertEqual(response.status_code, 200)
        
        # Simulate webhook with partial payment
        webhook_data = {
            'event': 'charge.success',
            'data': {
                'reference': 'test_ref',
                'amount': '500.00',
                'status': 'partial'
            }
        }
        
        response = self.client.post(
            reverse('core:paystack_webhook'),
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify investment was not completed
        self.assertEqual(Investment.objects.filter(status=Investment.Status.COMPLETED).count(), 0)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_expired_payment_completion(self, mock_create):
        """Test handling of expired payment completion"""
        mock_create.return_value = {'success': True, 'data': {'reference': 'test_ref'}}
        
        investment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'app_id': self.app_listing.id,
            'shares': '10'
        }
        
        response = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        self.assertEqual(response.status_code, 200)
        
        # Fast forward time to expire the payment
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now() + timezone.timedelta(hours=25)
            
            # Simulate webhook for expired payment
            webhook_data = {
                'event': 'charge.success',
                'data': {
                    'reference': 'test_ref',
                    'amount': '500.00',
                    'status': 'success'
                }
            }
            
            response = self.client.post(
                reverse('core:paystack_webhook'),
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
            
            # Verify response
            self.assertEqual(response.status_code, 400)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_duplicate_webhook_events(self, mock_create):
        """Test handling of duplicate webhook events"""
        mock_create.return_value = {'success': True, 'data': {'reference': 'test_ref'}}
        
        investment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'app_id': self.app_listing.id,
            'shares': '10'
        }
        
        response = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        self.assertEqual(response.status_code, 200)
        
        # Simulate webhook event twice
        webhook_data = {
            'event': 'charge.success',
            'data': {
                'reference': 'test_ref',
                'amount': '500.00',
                'status': 'success'
            }
        }
        
        # First webhook call
        response1 = self.client.post(
            reverse('core:paystack_webhook'),
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)
        
        # Second webhook call with same data
        response2 = self.client.post(
            reverse('core:paystack_webhook'),
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        
        # Verify only one investment was created
        self.assertEqual(Investment.objects.count(), 1)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_invalid_currency_conversion(self, mock_create):
        """Test handling of invalid currency conversion"""
        mock_create.return_value = {'success': True, 'data': {'reference': 'test_ref'}}
        
        investment_data = {
            'amount': '1000.00',
            'currency': 'XYZ',
            'app_id': self.app_listing.id,
            'shares': '10'
        }
        
        response = self.client.post(
            reverse('core:create_payment_intent'),
            data=investment_data
        )
        
        # Verify response
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported currency', str(response.content))

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_milestone_release_race_condition(self, mock_create):
        """Test handling of concurrent milestone releases"""
        # Setup initial investment
        escrow_tx = EscrowService.process_deposit(
            app=self.app_listing,
            investor=self.investor,
            amount=Decimal('500000.00'),
            currency='NGN'
        )
        
        # Create milestone
        milestone = ProjectMilestone.objects.create(
            app=self.app_listing,
            title='Test Milestone',
            description='Test milestone',
            release_percentage=Decimal('50.00')
        )
        
        # Simulate concurrent release requests
        with patch('django.db.transaction.atomic') as mock_atomic:
            # First release
            response1 = self.client.post(
                reverse('release_milestone', args=[milestone.id]),
                data={'action': 'release'}
            )
            
            # Second release (should fail)
            response2 = self.client.post(
                reverse('release_milestone', args=[milestone.id]),
                data={'action': 'release'}
            )
            
            # Verify responses
            self.assertEqual(response1.status_code, 200)
            self.assertEqual(response2.status_code, 400)
            
            # Verify only one release was processed
            releases = EscrowTransaction.objects.filter(
                app=self.app_listing,
                transaction_type='MILESTONE_RELEASE',
                milestone=milestone
            )
            self.assertEqual(releases.count(), 1) 
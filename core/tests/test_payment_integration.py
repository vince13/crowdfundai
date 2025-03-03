import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from ..models import (
    AppListing,
    Investment,
    EscrowTransaction,
    ShareOwnership,
    ProjectMilestone
)
from ..services.payments import PaymentService
from ..services.escrow import EscrowService
from datetime import timedelta
import json
import hmac
import hashlib

User = get_user_model()

class TestPaymentIntegration(TestCase):
    def setUp(self):
        """Set up test data."""
        # Override settings for testing
        self.paystack_secret = 'sk_test_123456789'
        self.settings_patcher = patch.dict('django.conf.settings.__dict__', {
            'PAYSTACK_SECRET_KEY': self.paystack_secret
        })
        self.settings_patcher.start()
        
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
            price_per_percentage=Decimal('500.00'),  # 500 NGN per 1%
            remaining_percentage=Decimal('20.00'),
            funding_end_date=timezone.now() + timedelta(days=30)
        )
        
        self.client.force_login(self.investor)

    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()

    @patch('core.services.payments.PaymentService.create_payment')
    def test_complete_investment_flow(self, mock_create_payment):
        """Test the complete investment flow from payment creation to webhook processing"""
        
        # 1. Mock payment creation response
        mock_create_payment.return_value = {
            'success': True,
            'authorization_url': 'https://paystack.com/pay/test',
            'access_code': 'test_access',
            'reference': 'test_ref_123'
        }
        
        # 2. Create payment intent
        payment_data = {
            'amount': '500.00',  # Amount for 1%
            'currency': 'NGN',
            'payment_type': 'investment',
            'app_id': str(self.app_listing.id),
            'percentage_amount': '1.00'  # Buying 1%
        }
        
        response = self.client.post(
            reverse('core:create_payment_intent'),
            data=json.dumps(payment_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # 3. Simulate Paystack webhook payload
        webhook_payload = {
            'event': 'charge.success',
            'data': {
                'reference': 'test_ref_123',
                'amount': 50000,  # Amount in kobo (500 NGN)
                'currency': 'NGN',
                'customer': {
                    'email': 'investor@example.com'
                },
                'metadata': {
                    'custom_fields': [
                        {
                            'variable_name': 'app_id',
                            'value': str(self.app_listing.id)
                        },
                        {
                            'variable_name': 'percentage_amount',
                            'value': '1.00'
                        },
                        {
                            'variable_name': 'payment_type',
                            'value': 'investment'
                        }
                    ]
                }
            }
        }
        
        # Mock Paystack signature verification
        with patch('hmac.new') as mock_hmac:
            mock_hmac.return_value.hexdigest.return_value = 'valid_signature'
            
            # 4. Send webhook request
            response = self.client.post(
                reverse('core:paystack_webhook'),
                data=json.dumps(webhook_payload),
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE='valid_signature'
            )
            
            self.assertEqual(response.status_code, 200)
        
        # 5. Verify investment was created
        investment = Investment.objects.filter(
            investor=self.investor,
            app=self.app_listing,
            percentage_bought=Decimal('1.00')
        ).first()
        
        self.assertIsNotNone(investment, "Investment record was not created")
        self.assertEqual(investment.amount_paid, Decimal('500.00'))
        self.assertEqual(investment.transaction_id, 'test_ref_123')
        
        # 6. Verify share ownership was updated
        ownership = ShareOwnership.objects.get(user=self.investor, app=self.app_listing)
        self.assertEqual(ownership.percentage_owned, Decimal('1.00'))
        
        # 7. Verify app's remaining percentage was updated
        self.app_listing.refresh_from_db()
        self.assertEqual(self.app_listing.remaining_percentage, Decimal('19.00'))
        
        # 8. Verify escrow transaction was created
        escrow = EscrowTransaction.objects.filter(
            app=self.app_listing,
            investor=self.investor,
            transaction_type=EscrowTransaction.Type.DEPOSIT,
            amount=Decimal('500.00')
        ).first()
        
        self.assertIsNotNone(escrow, "Escrow transaction was not created")
        self.assertEqual(escrow.status, 'COMPLETED')

    def test_milestone_release_flow(self):
        """Test milestone-based fund release flow"""
        # Setup: Create initial investment and escrow transaction
        escrow_tx = EscrowService.process_deposit(
            app=self.app_listing,
            investor=self.investor,
            amount=Decimal('500000.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='ref_123'
        )
        
        # Step 1: Mark milestone as completed
        self.milestone.progress = 100
        self.milestone.status = 'COMPLETED'
        self.milestone.save()
        
        # Step 2: Process milestone release
        self.client.login(email='developer@example.com', password='testpass123')
        
        with patch('services.payments.PaymentService._create_paystack_payment') as mock_create:
            mock_create.return_value = {
                'success': True,
                'reference': 'release_123'
            }
            
            response = self.client.post(
                reverse('process_milestone_release', kwargs={'milestone_id': self.milestone.id}),
                data={'release_percentage': '25.00'}
            )
            
            assert response.status_code == 200
        
        # Step 3: Verify release transaction
        release_tx = EscrowTransaction.objects.filter(
            app=self.app_listing,
            transaction_type='MILESTONE_RELEASE',
            milestone=self.milestone
        ).first()
        
        assert release_tx is not None
        assert release_tx.amount == Decimal('125000.00')  # 25% of 500000
        assert release_tx.status == 'COMPLETED'
        
        # Step 4: Verify updated escrow balance
        self.app_listing.refresh_from_db()
        assert self.app_listing.funds_in_escrow == Decimal('375000.00')  # 500000 - 125000

    def test_refund_flow(self):
        """Test refund flow"""
        # Setup: Create initial investment and escrow transaction
        escrow_tx = EscrowService.process_deposit(
            app=self.app_listing,
            investor=self.investor,
            amount=Decimal('500000.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='ref_123'
        )
        
        # Step 1: Process refund
        self.client.login(email='developer@example.com', password='testpass123')
        
        refund_data = {
            'transaction_id': escrow_tx.id,
            'refund_percentage': '50.00',
            'reason': 'Project scope reduced'
        }
        
        with patch('services.payments.PaymentService._create_paystack_payment') as mock_create:
            mock_create.return_value = {
                'success': True,
                'reference': 'refund_123'
            }
            
            response = self.client.post(
                reverse('process_refund'),
                data=refund_data
            )
            
            assert response.status_code == 200
        
        # Step 2: Verify refund transaction
        refund_tx = EscrowTransaction.objects.filter(
            app=self.app_listing,
            transaction_type='PARTIAL_REFUND',
            original_transaction=escrow_tx
        ).first()
        
        assert refund_tx is not None
        assert refund_tx.amount == Decimal('250000.00')  # 50% of 500000
        assert refund_tx.status == 'COMPLETED'
        
        # Step 3: Verify updated escrow balance
        self.app_listing.refresh_from_db()
        assert self.app_listing.funds_in_escrow == Decimal('250000.00')  # 500000 - 250000 

    @patch('core.services.payments.PaymentService.verify_payment')
    def test_investment_registration_flow(self, mock_verify_payment):
        """Test the complete investment registration flow including all related records."""
        # Login as investor
        self.client.login(username='investor', password='testpass123')
        
        # Setup test data
        investment_amount = Decimal('5000.00')
        percentage_amount = Decimal('10.00')  # 10% investment
        reference = 'test_ref_123'
        
        # Mock the payment verification response
        mock_verify_payment.return_value = {
            'success': True,
            'amount': investment_amount,
            'currency': 'NGN',
            'metadata': {
                'payment_type': 'investment',
                'app_id': str(self.app_listing.id),
                'user_id': str(self.investor.id),
                'percentage_amount': str(percentage_amount),
                'email': self.investor.email
            }
        }
        
        # Initial record counts
        initial_investment_count = Investment.objects.count()
        initial_escrow_count = EscrowTransaction.objects.count()
        initial_ownership_count = ShareOwnership.objects.count()
        
        # Simulate successful payment webhook
        webhook_data = {
            'event': 'charge.success',
            'data': {
                'reference': reference,
                'status': 'success',
                'amount': str(investment_amount * 100),  # Paystack amount in kobo
                'currency': 'NGN',
                'customer': {
                    'email': self.investor.email
                },
                'metadata': {
                    'payment_type': 'investment',
                    'app_id': str(self.app_listing.id),
                    'user_id': str(self.investor.id),
                    'percentage_amount': str(percentage_amount)
                }
            }
        }
        
        # Create webhook signature
        webhook_json = json.dumps(webhook_data)
        secret_key = self.paystack_secret.encode('utf-8')
        signature = hmac.new(
            secret_key,
            webhook_json.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # Call the webhook endpoint with proper signature
        response = self.client.post(
            reverse('core:paystack_webhook'),
            data=webhook_json,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Verify investment record
        self.assertEqual(Investment.objects.count(), initial_investment_count + 1)
        investment = Investment.objects.latest('created_at')
        self.assertEqual(investment.investor, self.investor)
        self.assertEqual(investment.app, self.app_listing)
        self.assertEqual(investment.amount_paid, investment_amount)
        self.assertEqual(investment.percentage_bought, percentage_amount)
        self.assertEqual(investment.transaction_id, reference)
        
        # Verify share ownership record
        self.assertEqual(ShareOwnership.objects.count(), initial_ownership_count + 1)
        ownership = ShareOwnership.objects.get(user=self.investor, app=self.app_listing)
        self.assertEqual(ownership.percentage_owned, percentage_amount)
        
        # Verify app listing updates
        self.app_listing.refresh_from_db()
        self.assertEqual(
            self.app_listing.remaining_percentage,
            Decimal('20.00') - percentage_amount  # Initial 20% - 10% invested
        )
        
        # If this was the last available share, verify app status changed to FUNDED
        if self.app_listing.remaining_shares == 0:
            self.assertEqual(self.app_listing.status, AppListing.Status.FUNDED)

    @patch('core.services.payments.PaymentService.verify_payment')
    def test_payment_verification_flow(self, mock_verify):
        """Test the complete payment verification flow."""
        self.client.login(username='investor', password='testpass123')
        
        # Mock payment verification response
        mock_verify.return_value = {
            'success': True,
            'amount': Decimal('2500.00'),  # Amount for 5%
            'currency': 'NGN',
            'metadata': {
                'payment_type': 'investment',
                'app_id': str(self.app_listing.id),
                'user_id': str(self.investor.id),
                'percentage_amount': '5.00'  # Buying 5% (minimum allowed)
            }
        }
        
        # Initial counts
        initial_investment_count = Investment.objects.count()
        initial_ownership_count = ShareOwnership.objects.count()
        
        # Verify payment
        response = self.client.get(
            reverse('core:verify_payment'),
            {'reference': 'test_ref_123'}
        )
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:portfolio'))
        
        # Verify investment was created
        self.assertEqual(Investment.objects.count(), initial_investment_count + 1)
        investment = Investment.objects.latest('created_at')
        self.assertEqual(investment.investor, self.investor)
        self.assertEqual(investment.app, self.app_listing)
        self.assertEqual(investment.percentage_bought, Decimal('5.00'))
        self.assertEqual(investment.amount_paid, Decimal('2500.00'))  # 5% * 500 per 1%
        
        # Verify share ownership was created
        self.assertEqual(ShareOwnership.objects.count(), initial_ownership_count + 1)
        ownership = ShareOwnership.objects.get(user=self.investor, app=self.app_listing)
        self.assertEqual(ownership.percentage_owned, Decimal('5.00'))
        
        # Verify app listing was updated
        self.app_listing.refresh_from_db()
        self.assertEqual(self.app_listing.remaining_percentage, Decimal('15.00'))  # 20% - 5%
        
        # Test when app becomes fully funded
        mock_verify.return_value['metadata']['percentage_amount'] = '15.00'  # Remaining 15%
        mock_verify.return_value['amount'] = Decimal('7500.00')  # 15% * 500 per 1%
        
        response = self.client.get(
            reverse('core:verify_payment'),
            {'reference': 'test_ref_456'}
        )
        
        self.app_listing.refresh_from_db()
        self.assertEqual(self.app_listing.remaining_percentage, Decimal('0.00'))
        self.assertEqual(self.app_listing.status, 'FUNDED') 
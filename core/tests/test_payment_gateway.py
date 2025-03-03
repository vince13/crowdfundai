import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from ..models import AppListing, Investment
from ..services.payments import PaymentService
from django.utils import timezone
import requests
import json
import hmac
import hashlib
from django.conf import settings

User = get_user_model()

class TestPaymentGateway(TestCase):
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
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        self.client.force_login(self.investor)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_create_payment(self, mock_create_payment):
        """Test payment creation"""
        # Mock successful payment creation
        mock_create_payment.return_value = {
            'success': True,
            'payment_url': 'https://paystack.com/pay/test',
            'reference': 'ref_123'
        }
        
        # Test data
        payment_data = {
            'amount': 1000.00,
            'currency': 'NGN',
            'metadata': {
                'payment_type': 'investment',
                'app_id': self.app_listing.id,
                'user_id': self.investor.id
            }
        }
        
        # Create payment
        result = PaymentService.create_payment(**payment_data)
        
        # Assertions
        assert result['success'] is True
        assert 'payment_url' in result
        assert 'reference' in result
        mock_create_payment.assert_called_once()

    @patch('core.services.payments.PaymentService._verify_paystack_payment')
    def test_verify_payment(self, mock_verify_payment):
        """Test payment verification"""
        # Mock successful verification
        mock_verify_payment.return_value = {
            'success': True,
            'status': 'success',
            'amount': 1000.00,
            'currency': 'NGN',
            'metadata': {
                'payment_type': 'investment',
                'app_id': str(self.app_listing.id)
            }
        }
        
        # Verify payment
        result = PaymentService.verify_payment('ref_123')
        
        # Assertions
        assert result['success'] is True
        assert result['status'] == 'success'
        assert 'amount' in result
        mock_verify_payment.assert_called_once_with('ref_123')

    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature"""
        webhook_data = {
            'event': 'charge.success',
            'data': {
                'reference': 'test_ref',
                'amount': '1000.00',
                'status': 'success'
            }
        }
        
        # Send webhook with invalid signature
        response = self.client.post(
            reverse('core:paystack_webhook'),
            data=json.dumps(webhook_data),
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='invalid_signature'
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_successful_payment(self):
        """Test webhook with successful payment"""
        webhook_data = {
            'event': 'charge.success',
            'data': {
                'reference': 'test_ref',
                'amount': '1000.00',
                'status': 'success'
            }
        }
        
        # Calculate valid signature
        payload = json.dumps(webhook_data).encode('utf-8')
        signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        # Send webhook with valid signature
        response = self.client.post(
            reverse('core:paystack_webhook'),
            data=json.dumps(webhook_data),
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature
        )
        self.assertEqual(response.status_code, 200)

    def test_payment_network_error(self):
        """Test payment creation with network error"""
        payment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'metadata': {
                'app_id': self.app_listing.id,
                'user_id': self.investor.id
            }
        }
        
        with patch('core.services.payments.PaymentService._create_paystack_payment', side_effect=requests.exceptions.ConnectionError):
            with pytest.raises(requests.exceptions.ConnectionError):
                PaymentService.create_payment(**payment_data)

    def test_payment_timeout(self):
        """Test payment creation with timeout"""
        payment_data = {
            'amount': '1000.00',
            'currency': 'NGN',
            'metadata': {
                'app_id': self.app_listing.id,
                'user_id': self.investor.id
            }
        }
        
        with patch('core.services.payments.PaymentService._create_paystack_payment', side_effect=requests.exceptions.Timeout):
            with pytest.raises(requests.exceptions.Timeout):
                PaymentService.create_payment(**payment_data)

    def test_invalid_amount(self):
        """Test payment creation with invalid amount"""
        payment_data = {
            'amount': '-1000.00',
            'currency': 'NGN',
            'metadata': {
                'app_id': self.app_listing.id,
                'user_id': self.investor.id
            }
        }
        
        with pytest.raises(ValueError):
            PaymentService.create_payment(**payment_data)

    @patch('core.services.payments.PaymentService._create_paystack_payment')
    def test_multi_currency_support(self, mock_create_payment):
        """Test payment creation with different currencies"""
        currencies = ['NGN', 'USD', 'EUR', 'GBP']
        
        for currency in currencies:
            payment_data = {
                'amount': 1000.00,
                'currency': currency,
                'metadata': {
                    'payment_type': 'investment',
                    'app_id': self.app_listing.id,
                    'user_id': self.investor.id
                }
            }
            
            PaymentService.create_payment(**payment_data)
            
        assert mock_create_payment.call_count == len(currencies) 
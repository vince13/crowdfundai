import json
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from core.forms import AppListingForm
from core.models.base import AppListing

class AppListingFormTest(TestCase):
    def setUp(self):
        self.valid_form_data = {
            'name': 'Test App',
            'category': 'CHATBOT',
            'description': 'A test app description',
            'ai_features': 'Test AI features',
            'github_url': 'https://github.com/test/test-app',
            'demo_url': 'https://test-app.com',
            'funding_goal': 1000000,  # $1M
            'currency': 'USD',
            'available_percentage': 20.0,
            'min_investment_percentage': 5.0,
            'equity_percentage': 25.0,
            'funding_round': 'PRESEED',
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': (timezone.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
            'use_of_funds': json.dumps({
                'Development': 40,
                'Marketing': 30,
                'Operations': 30
            })
        }

    def test_valid_form(self):
        """Test form with valid data."""
        form_data = {
            'name': 'Test App',
            'description': 'Test Description',
            'ai_features': 'Test AI Features',
            'category': 'OTHER',  # Valid choice from model
            'funding_goal': '10000.00',
            'currency': 'NGN',  # Valid choice from model
            'available_percentage': '20.00',
            'min_investment_percentage': '1.00',
            'equity_percentage': '100.00',
            'price_per_percentage': '500.00',
            'funding_round': 'PRESEED',  # Valid choice from model
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': timezone.now() + timezone.timedelta(days=30),
            'use_of_funds': json.dumps({'development': 60, 'marketing': 40})
        }
        form = AppListingForm(data=form_data)
        self.assertTrue(form.is_valid())
        
    def test_invalid_min_investment(self):
        """Test form with invalid minimum investment."""
        form_data = {
            'name': 'Test App',
            'description': 'Test Description',
            'ai_features': 'Test AI Features',
            'category': 'OTHER',
            'funding_goal': '10000.00',
            'currency': 'NGN',
            'available_percentage': '20.00',
            'min_investment_percentage': '0.00',  # Invalid - less than 1%
            'equity_percentage': '100.00',
            'price_per_percentage': '500.00',
            'funding_round': 'PRESEED',
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': timezone.now() + timezone.timedelta(days=30),
            'use_of_funds': json.dumps({'development': 60, 'marketing': 40})
        }
        form = AppListingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('min_investment_percentage', form.errors)
        
    def test_invalid_funding_end_date(self):
        """Test form with invalid funding end date."""
        form_data = {
            'name': 'Test App',
            'description': 'Test Description',
            'ai_features': 'Test AI Features',
            'category': 'OTHER',
            'funding_goal': '10000.00',
            'currency': 'NGN',
            'available_percentage': '20.00',
            'min_investment_percentage': '1.00',
            'equity_percentage': '100.00',
            'price_per_percentage': '500.00',
            'funding_round': 'PRESEED',
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': timezone.now() - timezone.timedelta(days=1),  # Invalid - past date
            'use_of_funds': json.dumps({'development': 60, 'marketing': 40})
        }
        form = AppListingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('funding_end_date', form.errors)
        
    def test_invalid_use_of_funds_total(self):
        """Test form with invalid use of funds total."""
        form_data = {
            'name': 'Test App',
            'description': 'Test Description',
            'ai_features': 'Test AI Features',
            'category': 'OTHER',
            'funding_goal': '10000.00',
            'currency': 'NGN',
            'available_percentage': '20.00',
            'min_investment_percentage': '1.00',
            'equity_percentage': '100.00',
            'price_per_percentage': '500.00',
            'funding_round': 'PRESEED',
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': timezone.now() + timezone.timedelta(days=30),
            'use_of_funds': json.dumps({'development': 50, 'marketing': 40})  # Invalid - total < 100%
        }
        form = AppListingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('use_of_funds', form.errors)
        
    def test_invalid_use_of_funds_empty_category(self):
        """Test form with empty use of funds category."""
        form_data = {
            'name': 'Test App',
            'description': 'Test Description',
            'ai_features': 'Test AI Features',
            'category': 'OTHER',
            'funding_goal': '10000.00',
            'currency': 'NGN',
            'available_percentage': '20.00',
            'min_investment_percentage': '1.00',
            'equity_percentage': '100.00',
            'price_per_percentage': '500.00',
            'funding_round': 'PRESEED',
            'round_number': 1,
            'lock_in_period': 180,
            'funding_end_date': timezone.now() + timezone.timedelta(days=30),
            'use_of_funds': json.dumps({'': 100})  # Invalid - empty category
        }
        form = AppListingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('use_of_funds', form.errors) 
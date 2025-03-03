from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from core.models import Advertisement
from core.forms import AdvertisementForm

User = get_user_model()

class AdvertisementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Set up test data
        self.ad_data = {
            'title': 'Test Advertisement',
            'company_name': 'Test Company',
            'contact_email': 'test@example.com',
            'position': 'main',
            'target_url': 'https://example.com',
            'content': '<p>Test content</p>',
            'start_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            'cta': 'Learn More'
        }

    def test_create_advertisement(self):
        """Test creating a new advertisement"""
        # Get the form page
        response = self.client.get(reverse('core:ad_create'))
        self.assertEqual(response.status_code, 200)
        
        # Submit the form
        response = self.client.post(
            reverse('core:ad_create'),
            data=self.ad_data,
            follow=True
        )
        
        # Print form errors if any
        if 'form' in response.context:
            form = response.context['form']
            if not form.is_valid():
                print("Form Errors:", form.errors)
        
        # Check if ad was created
        self.assertTrue(Advertisement.objects.exists())
        ad = Advertisement.objects.first()
        self.assertEqual(ad.title, self.ad_data['title'])
        self.assertEqual(ad.advertiser, self.user)

    def test_form_validation(self):
        """Test form validation"""
        form = AdvertisementForm(data=self.ad_data, user=self.user)
        
        # Print any form errors
        if not form.is_valid():
            print("Form Validation Errors:", form.errors)
        
        self.assertTrue(form.is_valid())

    def test_missing_required_fields(self):
        """Test form validation with missing required fields"""
        # Remove required fields one by one and check error messages
        required_fields = ['title', 'company_name', 'contact_email', 'position', 'target_url', 'content']
        
        for field in required_fields:
            data = self.ad_data.copy()
            data.pop(field)
            form = AdvertisementForm(data=data, user=self.user)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_invalid_dates(self):
        """Test form validation with invalid dates"""
        # Test past start date
        data = self.ad_data.copy()
        data['start_date'] = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        form = AdvertisementForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        
        # Test end date before start date
        data = self.ad_data.copy()
        data['end_date'] = (timezone.now()).strftime('%Y-%m-%d')
        data['start_date'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        form = AdvertisementForm(data=data, user=self.user)
        self.assertFalse(form.is_valid()) 
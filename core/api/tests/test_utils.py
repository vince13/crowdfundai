from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import User, AppListing, Investment

class BaseAPITestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='INVESTOR'
        )
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            developer=self.user
        )
        self.investment = Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount=1000.00,
            shares=10
        ) 
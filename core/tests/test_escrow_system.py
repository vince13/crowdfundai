from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from core.models import User, AppListing

class EscrowSystemTests(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@example.com',
            password='testpass123',
            role=User.Role.DEVELOPER
        )
        self.investor = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='testpass123',
            role=User.Role.INVESTOR
        )
        
        # Create test app listing
        self.app_listing = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            ai_features='Test AI Features',
            developer=self.developer,
            funding_goal=Decimal('10000.00'),
            currency='NGN',
            exchange_rate=Decimal('1.0000'),
            available_percentage=Decimal('20.00'),
            min_investment_percentage=Decimal('1.00'),
            equity_percentage=Decimal('20.00'),
            remaining_percentage=Decimal('20.00'),
            price_per_percentage=Decimal('500.00'),
            funding_round='PRESEED',
            round_number=1,
            lock_in_period=180,
            funding_end_date=timezone.now() + timezone.timedelta(days=30),
            use_of_funds={'development': 100}
        ) 
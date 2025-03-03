from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import AppListing, Investment, Transaction, ShareOwnership
from django.db.models import Sum
from django.utils import timezone

User = get_user_model()

class InvestmentTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test app listing with all required fields
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            developer=self.user,
            funding_goal=Decimal('10000.00'),
            available_percentage=Decimal('13.00'),
            equity_percentage=Decimal('13.00'),
            min_investment_percentage=Decimal('1.00'),
            status=AppListing.Status.ACTIVE,
            project_status=AppListing.Status.ACTIVE,
            exchange_rate=Decimal('1.00'),
            currency=AppListing.Currency.NGN,
            funding_round=AppListing.FundingRound.PRESEED,
            category=AppListing.Category.OTHER,
            listing_type=AppListing.ListingType.LISTED,
            development_stage=AppListing.DevelopmentStage.CONCEPT,
            lock_in_period=180,
            ai_features='Test AI Features',
            remaining_percentage=Decimal('13.00'),
            price_per_percentage=Decimal('769.23'),  # 10000/13
            funding_end_date=timezone.now() + timezone.timedelta(days=30),
            escrow_status='COLLECTING'
        )
        
    def test_initial_investment(self):
        """Test that initial investment works correctly"""
        # Calculate amount for 1% based on company valuation
        company_valuation = self.app.get_company_valuation()
        amount_for_one_percent = company_valuation / Decimal('100.0')
        
        # Create initial investment of 1%
        investment = Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=amount_for_one_percent,
            transaction_id='test_transaction_1'
        )
        
        # Refresh app instance from database
        self.app.refresh_from_db()
        
        # Verify investment was created correctly
        self.assertEqual(investment.percentage_bought, Decimal('1.00'))
        self.assertEqual(self.app.remaining_percentage, Decimal('12.00'))
        
        # Verify share ownership was created
        ownership = ShareOwnership.objects.get(user=self.user, app=self.app)
        self.assertEqual(ownership.percentage_owned, Decimal('1.00'))
    
    def test_multiple_investments(self):
        """Test that multiple investments work correctly"""
        company_valuation = self.app.get_company_valuation()
        amount_for_one_percent = company_valuation / Decimal('100.0')
        
        # Make first investment of 1%
        Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=amount_for_one_percent,
            transaction_id='test_transaction_1'
        )
        
        # Make second investment of 2%
        Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=amount_for_one_percent * 2,
            transaction_id='test_transaction_2'
        )
        
        # Refresh app instance from database
        self.app.refresh_from_db()
        
        # Verify remaining percentage
        self.assertEqual(self.app.remaining_percentage, Decimal('10.00'))
        
        # Verify total investment
        total_invested = Investment.objects.filter(app=self.app).aggregate(
            total=Sum('percentage_bought')
        )['total']
        self.assertEqual(total_invested, Decimal('3.00'))
    
    def test_investment_exceeding_remaining_percentage(self):
        """Test that investing more than remaining percentage fails"""
        company_valuation = self.app.get_company_valuation()
        
        # Try to invest more than available percentage
        amount_for_fifteen_percent = (company_valuation / Decimal('100.0')) * Decimal('15.0')
        
        with self.assertRaises(ValueError) as context:
            Investment.objects.create(
                investor=self.user,
                app=self.app,
                amount_paid=amount_for_fifteen_percent,
                transaction_id='test_transaction_1'
            )
        
        self.assertTrue('Cannot invest more than the remaining percentage' in str(context.exception))
    
    def test_investment_after_partial_funding(self):
        """Test investing remaining percentage after partial funding"""
        company_valuation = self.app.get_company_valuation()
        amount_for_one_percent = company_valuation / Decimal('100.0')
        
        # First investment of 10%
        Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=amount_for_one_percent * 10,
            transaction_id='test_transaction_1'
        )
        
        # Refresh app instance from database
        self.app.refresh_from_db()
        
        # Verify remaining percentage is 3%
        self.assertEqual(self.app.remaining_percentage, Decimal('3.00'))
        
        # Try to invest exactly 3%
        Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=amount_for_one_percent * 3,
            transaction_id='test_transaction_2'
        )
        
        # Refresh app instance from database
        self.app.refresh_from_db()
        
        # Verify app is fully funded
        self.assertEqual(self.app.remaining_percentage, Decimal('0.00'))
        self.assertEqual(self.app.status, AppListing.Status.FUNDED) 

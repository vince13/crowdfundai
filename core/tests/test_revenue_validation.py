import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Revenue, Distribution
from core.services.revenue.distribution import RevenueDistributionService

@pytest.mark.django_db
class TestRevenueValidation:
    @pytest.fixture(autouse=True)
    def setup(self, client, developer_user):
        self.client = client
        self.developer = developer_user
        
        self.app = AppListing.objects.create(
            developer=self.developer,
            name="Test App",
            description="Test Description",
            funding_goal=Decimal("10000.00"),
            price_per_percentage=Decimal("500.00"),
            available_percentage=Decimal("20.00"),
            equity_percentage=Decimal("100.00"),
            min_investment_percentage=Decimal("1.00"),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        self.distribution_service = RevenueDistributionService()

    def test_negative_amount(self):
        """Test validation of negative revenue amounts"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("-100.00"),
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)
            )

    def test_invalid_period_dates(self):
        """Test validation of invalid period dates"""
        end_date = timezone.now()
        start_date = end_date + timezone.timedelta(days=1)  # Start after end
        
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("100.00"),
                period_start=start_date,
                period_end=end_date
            )

    def test_future_period(self):
        """Test validation of future period dates"""
        future_start = timezone.now() + timezone.timedelta(days=30)
        future_end = future_start + timezone.timedelta(days=30)
        
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("100.00"),
                period_start=future_start,
                period_end=future_end
            )

    def test_zero_amount(self):
        """Test validation of zero amount"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("0.00"),
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)
            )

    def test_missing_required_fields(self):
        """Test validation of missing required fields"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("100.00")
                # Missing period_start and period_end
            )

    def test_duplicate_period(self):
        """Test validation of overlapping periods"""
        period_start = timezone.now()
        period_end = period_start + timezone.timedelta(days=30)
        
        # Create first revenue
        Revenue.objects.create(
            app=self.app,
            amount=Decimal("100.00"),
            period_start=period_start,
            period_end=period_end
        )
        
        # Try to create overlapping revenue
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("200.00"),
                period_start=period_start + timezone.timedelta(days=15),
                period_end=period_end + timezone.timedelta(days=15)
            )

    def test_revenue_validation(self, app_listing, investor):
        """Test revenue validation"""
        app = AppListing.objects.create(
            name="Test App",
            description="A test app",
            developer=app_listing.developer,
            funding_goal=Decimal("10000.00"),
            currency='NGN',
            price_per_percentage=Decimal("500.00"),
            available_percentage=Decimal("20.00"),
            equity_percentage=Decimal("100.00"),
            min_investment_percentage=Decimal("1.00"),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        ) 
import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Revenue, Distribution
from core.services.revenue.distribution import RevenueDistributionService

@pytest.mark.django_db
class TestRevenueErrorCases:
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

    def test_negative_revenue_amount(self):
        """Test handling of negative revenue amounts"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("-1000.00"),
                currency='NGN',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)
            )

    def test_invalid_currency_code(self):
        """Test handling of invalid currency codes"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency='INVALID',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)
            )

    def test_overlapping_periods(self):
        """Test handling of overlapping revenue periods"""
        period_start = timezone.now()
        period_end = period_start + timezone.timedelta(days=30)

        # Create first revenue record
        Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=period_start,
            period_end=period_end
        )

        # Attempt to create overlapping revenue record
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("2000.00"),
                currency='NGN',
                period_start=period_start + timezone.timedelta(days=15),
                period_end=period_end + timezone.timedelta(days=15)
            )

    def test_redistribution_attempt(self):
        """Test attempt to redistribute already distributed revenue"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30)
        )

        # First distribution should succeed
        result = self.distribution_service.process_distribution(revenue.id)
        assert result is True

        # Second distribution attempt should fail
        with pytest.raises(ValidationError):
            self.distribution_service.process_distribution(revenue.id)

    def test_invalid_revenue_id(self):
        """Test distribution with invalid revenue ID"""
        invalid_id = 99999  # Non-existent ID
        with pytest.raises(Revenue.DoesNotExist):
            self.distribution_service.process_distribution(invalid_id)

    def test_zero_amount_revenue(self):
        """Test handling of zero amount revenue"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("0.00"),
                currency='NGN',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)
            )

    def test_error_case_revenue_distribution(self):
        """Test error case revenue distribution"""
        app = AppListing.objects.create(
            name="Test App",
            description="A test app",
            developer=self.developer,
            funding_goal=Decimal("10000.00"),
            currency='NGN',
            price_per_percentage=Decimal("500.00"),
            available_percentage=Decimal("20.00"),
            equity_percentage=Decimal("100.00"),
            min_investment_percentage=Decimal("1.00"),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        ) 
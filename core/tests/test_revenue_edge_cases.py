import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Revenue, Distribution
from core.services.revenue.distribution import RevenueDistributionService

@pytest.mark.django_db
class TestRevenueBasics:
    @pytest.fixture(autouse=True)
    def setup(self, client, developer_user):
        """Set up test data"""
        self.client = client
        self.developer = developer_user
        
        # Create an app
        self.app = AppListing.objects.create(
            developer=self.developer,
            name="Test App",
            description="Test Description",
            funding_goal=Decimal("10000.00"),
            share_price=Decimal("100.00"),
            total_shares=100,
            equity_percentage=Decimal("10.00"),
            exchange_rate=Decimal("750.00")
        )

    def test_basic_revenue_creation(self):
        """Test basic revenue record creation"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        assert revenue.amount == Decimal("1000.00")
        assert revenue.currency == 'NGN'
        assert revenue.metadata['source'] == 'test'

    def test_basic_distribution(self):
        """Test basic distribution processing"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        result = service.process_distribution(revenue.id)
        assert result is True
        assert revenue.is_distributed

    def test_distribution_total(self):
        """Test distribution total matches revenue amount"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        service.process_distribution(revenue.id)
        
        distributions = Distribution.objects.filter(revenue=revenue)
        total_distributed = sum(d.amount for d in distributions)
        assert total_distributed == revenue.amount

@pytest.mark.django_db
class TestRevenueErrorCases:
    @pytest.fixture(autouse=True)
    def setup(self, client, developer_user):
        """Set up test data"""
        self.client = client
        self.developer = developer_user
        
        # Create an app
        self.app = AppListing.objects.create(
            developer=self.developer,
            name="Test App",
            description="Test Description",
            funding_goal=Decimal("10000.00"),
            share_price=Decimal("100.00"),
            total_shares=100,
            equity_percentage=Decimal("10.00"),
            exchange_rate=Decimal("750.00")
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
            period_end=period_end,
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )

        # Try to create overlapping revenue record
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("500.00"),
                currency='NGN',
                period_start=period_start + timezone.timedelta(days=15),
                period_end=period_end + timezone.timedelta(days=15),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("750.00")
            )

    def test_redistribution_attempt(self):
        """Test attempt to redistribute already distributed revenue"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        
        # First distribution should succeed
        result = service.process_distribution(revenue.id)
        assert result is True
        
        # Second distribution should fail
        with pytest.raises(ValidationError):
            service.process_distribution(revenue.id)

def test_edge_case_revenue_distribution(app_listing, investor):
    """Test edge case revenue distribution"""
    app = AppListing.objects.create(
        name="Test App",
        description="A test app",
        developer=app_listing.developer,
        funding_goal=Decimal("10000.00"),
        currency='NGN',
        exchange_rate=Decimal("750.00"),
        price_per_percentage=Decimal("500.00"),
        available_percentage=Decimal("20.00"),
        equity_percentage=Decimal("100.00"),
        min_investment_percentage=Decimal("1.00"),
        funding_end_date=timezone.now() + timezone.timedelta(days=30)
    ) 
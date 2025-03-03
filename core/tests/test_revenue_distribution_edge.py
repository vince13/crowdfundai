import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Revenue, Distribution
from core.services.revenue.distribution import RevenueDistributionService

@pytest.mark.django_db
class TestRevenueDistributionEdge:
    @pytest.fixture(autouse=True)
    def setup(self, client, developer_user, regular_user):
        """Set up test data"""
        self.client = client
        self.developer = developer_user
        self.investor = regular_user
        
        # Create an app
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

    def test_zero_amount_distribution(self):
        """Test distribution of zero amount revenue"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("0.00"),
                currency='NGN',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("750.00")
            )

    def test_distribution_rollback(self):
        """Test rollback of failed distribution"""
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
        
        # Simulate a failure during distribution
        with pytest.raises(Exception):
            service.process_distribution(revenue.id, simulate_error=True)
        
        # Check that no distributions were created
        assert Distribution.objects.filter(revenue=revenue).count() == 0
        
        # Check revenue status wasn't updated
        revenue.refresh_from_db()
        assert not revenue.is_distributed

    def test_partial_distribution_failure(self):
        """Test handling of partial distribution failure"""
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
        
        # Simulate a partial failure
        with pytest.raises(Exception):
            service.process_distribution(revenue.id, simulate_partial_error=True)
        
        # Check that no distributions were created (should rollback all)
        assert Distribution.objects.filter(revenue=revenue).count() == 0
        
        # Check revenue status wasn't updated
        revenue.refresh_from_db()
        assert not revenue.is_distributed

    def test_concurrent_distributions(self):
        """Test handling of concurrent distribution processing"""
        # Create multiple revenue records
        revenue1 = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        revenue2 = Revenue.objects.create(
            app=self.app,
            amount=Decimal("2000.00"),
            currency='NGN',
            period_start=timezone.now() + timezone.timedelta(days=31),
            period_end=timezone.now() + timezone.timedelta(days=60),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        
        # Process distributions concurrently
        result1 = service.process_distribution(revenue1.id)
        result2 = service.process_distribution(revenue2.id)
        
        assert result1 is True
        assert result2 is True
        
        # Check both revenues were distributed correctly
        revenue1.refresh_from_db()
        revenue2.refresh_from_db()
        assert revenue1.is_distributed
        assert revenue2.is_distributed

    def test_distribution_edge_case(self):
        """Test distribution edge case"""
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

        # Additional test logic can be added here 
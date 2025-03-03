import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Revenue, Distribution, ShareOwnership, User
from core.services.revenue.distribution import RevenueDistributionService

@pytest.mark.django_db
class TestRevenueCurrencyCases:
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
            price_per_percentage=Decimal("500.00"),
            available_percentage=Decimal("20.00"),
            equity_percentage=Decimal("100.00"),
            min_investment_percentage=Decimal("1.00"),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Create share ownership records for testing distributions
        ShareOwnership.objects.create(
            user=self.developer,
            app=self.app,
            shares_owned=60  # 60% ownership
        )
        
        # Create another user and share ownership for testing
        self.investor = User.objects.create_user(
            username='test_investor',
            email='investor@test.com',
            password='testpass123'
        )
        ShareOwnership.objects.create(
            user=self.investor,
            app=self.app,
            shares_owned=40  # 40% ownership
        )

    def test_usd_revenue_distribution(self):
        """Test revenue distribution with USD currency"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='USD',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        result = service.process_distribution(revenue.id)
        assert result is True
        
        # Check USD amount was converted correctly
        distributions = Distribution.objects.filter(revenue=revenue)
        total_distributed = sum(d.amount for d in distributions)
        assert total_distributed == revenue.amount

    def test_mixed_currency_revenues(self):
        """Test handling of revenues in different currencies"""
        # Create USD revenue
        start_time = timezone.now()
        usd_revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            currency='USD',
            period_start=start_time,
            period_end=start_time + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        # Create NGN revenue with non-overlapping period
        ngn_revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("750000.00"),  # 1000 USD equivalent
            currency='NGN',
            period_start=start_time + timezone.timedelta(days=31),
            period_end=start_time + timezone.timedelta(days=60),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        # Test USD to NGN conversion
        ngn_equivalent = usd_revenue.amount * usd_revenue.exchange_rate
        assert ngn_equivalent == Decimal("750000.00")
        
        # Test NGN to USD conversion
        usd_equivalent = ngn_revenue.amount / ngn_revenue.exchange_rate
        assert usd_equivalent == Decimal("1000.00")

    def test_zero_decimal_currency(self):
        """Test handling of currencies with no decimal places"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency='JPY',  # Japanese Yen has no decimals
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("750.00")
            )

    def test_high_precision_conversion(self):
        """Test handling of high precision currency conversions"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.123"),  # More than 2 decimal places
                currency='USD',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("750.00")
            ) 

    def test_negative_exchange_rate(self):
        """Test validation of negative exchange rates"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency='USD',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("-750.00")
            )

    def test_invalid_currency_code(self):
        """Test validation of invalid currency codes"""
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency='INVALID',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("750.00")
            )

    def test_currency_rounding(self):
        """Test proper rounding of currency amounts in distributions"""
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("999.99"),
            currency='USD',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        service.process_distribution(revenue.id)
        
        distributions = Distribution.objects.filter(revenue=revenue)
        total_distributed = sum(d.amount for d in distributions)
        
        # Check that rounding maintains exact amounts
        assert total_distributed == revenue.amount
        # Verify individual distributions are rounded to 2 decimal places
        for dist in distributions:
            decimal_places = abs(dist.amount.as_tuple().exponent)
            assert decimal_places <= 2 

    def test_stale_exchange_rate(self):
        """Test handling of stale exchange rates (older than 24 hours)"""
        stale_date = timezone.now() - timezone.timedelta(hours=25)
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency='EUR',
                period_start=stale_date,
                period_end=stale_date + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web', 'exchange_rate_timestamp': stale_date},
                exchange_rate=Decimal("1.10")
            )

    def test_large_currency_difference(self):
        """Test handling of currencies with large value differences"""
        # Test with Bitcoin to Vietnamese Dong conversion
        large_amount = Decimal("1000000000.00")  # 1 billion VND
        revenue = Revenue.objects.create(
            app=self.app,
            amount=large_amount,
            currency='VND',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("0.000041")  # VND to USD rate
        )
        
        service = RevenueDistributionService()
        result = service.process_distribution(revenue.id)
        assert result is True
        
        distributions = Distribution.objects.filter(revenue=revenue)
        total_distributed = sum(d.amount for d in distributions)
        assert total_distributed == revenue.amount

    def test_multi_currency_aggregation(self):
        """Test aggregation of revenues in different currencies"""
        # Create revenues in different currencies with non-overlapping periods
        start_time = timezone.now()
        currencies = [
            ('USD', Decimal("1000.00"), Decimal("1.00"), 0),
            ('EUR', Decimal("900.00"), Decimal("1.10"), 31),
            ('GBP', Decimal("800.00"), Decimal("1.25"), 62)
        ]
        
        for currency, amount, rate, days_offset in currencies:
            period_start = start_time + timezone.timedelta(days=days_offset)
            period_end = period_start + timezone.timedelta(days=30)
            Revenue.objects.create(
                app=self.app,
                amount=amount,
                currency=currency,
                period_start=period_start,
                period_end=period_end,
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=rate
            )
        
        # Test total revenue calculation in USD
        total_usd = sum(
            revenue.amount * revenue.exchange_rate 
            for revenue in Revenue.objects.filter(app=self.app)
        )
        
        assert total_usd == Decimal("2890.00")  # 1000 + (900 * 1.10) + (800 * 1.25)

    def test_currency_display_formatting(self):
        """Test currency display formatting for different currencies"""
        # Create revenues in different currencies with non-overlapping periods
        start_time = timezone.now()
        test_cases = [
            ('NGN', Decimal("50000.00"), "₦50,000.00", 0),  # Naira with comma
            ('USD', Decimal("1000.50"), "$1,000.50", 31),    # USD with comma
            ('JPY', Decimal("100000"), "¥100,000", 62),      # Yen with no decimals
            ('EUR', Decimal("1234.56"), "€1,234.56", 93)     # Euro with comma
        ]
        
        for currency_code, amount, expected_format, days_offset in test_cases:
            period_start = start_time + timezone.timedelta(days=days_offset)
            period_end = period_start + timezone.timedelta(days=30)
            revenue = Revenue.objects.create(
                app=self.app,
                amount=amount,
                currency=currency_code,
                period_start=period_start,
                period_end=period_end,
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("1.00")
            )
            assert revenue.get_formatted_amount() == expected_format

    def test_naira_specific_rules(self):
        """Test Naira-specific validation rules"""
        # Test minimum amount rule for Naira (assuming minimum is 100 NGN)
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("50.00"),
                currency='NGN',
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30),
                metadata={'source': 'test', 'platform': 'web'},
                exchange_rate=Decimal("1.00")
            )
        
        # Test valid Naira amount with kobo (2 decimal places)
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.50"),
            currency='NGN',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("1.00")
        )
        assert revenue.amount.as_tuple().exponent == -2  # Verify 2 decimal places

    def test_currency_symbol_handling(self):
        """Test handling of currency symbols in metadata and display"""
        start_time = timezone.now()
        symbols = {
            'NGN': ('₦', 0),
            'USD': ('$', 31),
            'EUR': ('€', 62),
            'GBP': ('£', 93),
            'JPY': ('¥', 124)
        }
        
        for currency, (symbol, days_offset) in symbols.items():
            period_start = start_time + timezone.timedelta(days=days_offset)
            period_end = period_start + timezone.timedelta(days=30)
            revenue = Revenue.objects.create(
                app=self.app,
                amount=Decimal("1000.00"),
                currency=currency,
                period_start=period_start,
                period_end=period_end,
                metadata={
                    'source': 'test',
                    'platform': 'web',
                    'display_symbol': symbol
                },
                exchange_rate=Decimal("1.00")
            )
            
            # Test that the symbol is correctly stored and retrieved
            assert revenue.metadata['display_symbol'] == symbol
            # Test that the symbol is correctly used in formatting
            assert revenue.get_formatted_amount().startswith(symbol)

    def test_naira_conversion_rules(self):
        """Test specific rules for converting to and from Naira"""
        # Test conversion from USD to NGN
        usd_revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("100.00"),
            currency='USD',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")  # 1 USD = 750 NGN
        )
        
        # Verify the NGN equivalent is correctly calculated
        ngn_equivalent = usd_revenue.amount * usd_revenue.exchange_rate
        assert ngn_equivalent == Decimal("75000.00")
        
        # Test that converted amount maintains 2 decimal places
        assert ngn_equivalent.quantize(Decimal('0.01')) == Decimal("75000.00")
        
        # Verify distribution amounts also maintain proper Naira formatting
        service = RevenueDistributionService()
        service.process_distribution(usd_revenue.id)
        
        distributions = Distribution.objects.filter(revenue=usd_revenue)
        for dist in distributions:
            # Verify each distribution amount has proper decimal places
            assert dist.amount.quantize(Decimal('0.01')) == dist.amount 

    def test_currency_case_revenue_distribution(self):
        """Test currency case revenue distribution"""
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

        revenue = Revenue.objects.create(
            app=app,
            amount=Decimal("1000.00"),
            currency='USD',
            period_start=timezone.now(),
            period_end=timezone.now() + timezone.timedelta(days=30),
            metadata={'source': 'test', 'platform': 'web'},
            exchange_rate=Decimal("750.00")
        )
        
        service = RevenueDistributionService()
        result = service.process_distribution(revenue.id)
        assert result is True
        
        # Check USD amount was converted correctly
        distributions = Distribution.objects.filter(revenue=revenue)
        total_distributed = sum(d.amount for d in distributions)
        assert total_distributed == revenue.amount 
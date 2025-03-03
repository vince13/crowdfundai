import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import AppListing, Investment, Revenue, Distribution, ShareOwnership, Notification, User
from core.services.revenue.distribution import RevenueDistributionService
from django.test import TestCase, Client
import json

@pytest.mark.django_db
class TestRevenueDistribution:
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
            currency='NGN',
            exchange_rate=Decimal("1.00"),
            price_per_percentage=Decimal("500.00"),
            available_percentage=Decimal("20.00"),
            equity_percentage=Decimal("100.00"),
            min_investment_percentage=Decimal("1.00"),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Create an investment
        self.investment = Investment.objects.create(
            investor=self.investor,
            app=self.app,
            shares=10,
            amount=Decimal("1000.00")
        )
        
        # Create revenue record
        self.revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            period_start=timezone.now().replace(day=1),
            period_end=timezone.now(),
            status="PENDING"
        )
        
        self.distribution_service = RevenueDistributionService()

    def test_revenue_creation(self):
        """Test revenue record creation"""
        assert self.revenue.app == self.app
        assert self.revenue.amount == Decimal("1000.00")
        assert self.revenue.status == "PENDING"

    def test_distribution_calculation(self):
        """Test revenue distribution calculation"""
        distribution = self.distribution_service.calculate_share_distribution(self.app, self.revenue.amount)
        
        # Developer should get 90% of revenue when they hold 90 shares
        developer_share = next(d for d in distribution if d['recipient'] == self.developer)
        assert developer_share['share_percentage'] == Decimal('90')
        assert developer_share['amount'] == Decimal('900.00')
        
        # Investor should get 10% of revenue when they hold 10 shares
        investor_share = next(d for d in distribution if d['recipient'] == self.investor)
        assert investor_share['share_percentage'] == Decimal('10')
        assert investor_share['amount'] == Decimal('100.00')

    def test_distribution_processing(self):
        """Test revenue distribution processing"""
        # Process the distribution
        result = self.distribution_service.process_distribution(self.revenue.id)
        assert result is True
        
        # Check distributions were created
        distributions = Distribution.objects.filter(revenue=self.revenue)
        assert distributions.count() == 2  # One for developer, one for investor
        
        # Check distribution amounts
        total_distributed = sum(d.amount for d in distributions)
        assert total_distributed == self.revenue.amount
        
        # Check revenue status was updated
        self.revenue.refresh_from_db()
        assert self.revenue.is_distributed is True

    def test_revenue_validation(self):
        """Test revenue validation"""
        # Try to create revenue with invalid amount
        with pytest.raises(ValidationError):
            Revenue.objects.create(
                app=self.app,
                amount=Decimal("-100.00"),  # Negative amount should raise error
                period_start=timezone.now().replace(day=1),
                period_end=timezone.now()
            )

    def test_distribution_api(self):
        """Test revenue distribution API endpoints"""
        self.client.force_login(self.developer)
        
        # Test revenue list view
        response = self.client.get(reverse('core:revenue_dashboard'))
        assert response.status_code == 200
        
        # Test revenue detail view
        response = self.client.get(
            reverse('core:revenue_detail', kwargs={'pk': self.revenue.pk})
        )
        assert response.status_code == 200
        
        # Test distribution processing endpoint
        response = self.client.post(
            reverse('core:process_distributions', kwargs={'pk': self.app.pk})
        )
        assert response.status_code == 200
        assert response.json()['success'] is True

    def test_retry_failed_distribution(self):
        """Test retrying a failed distribution"""
        # Create a failed distribution
        distribution = Distribution.objects.create(
            revenue=self.revenue,
            recipient=self.investor,
            amount=Decimal("100.00"),
            share_percentage=Decimal("10.00"),
            status='FAILED',
            error_message="Test error"
        )
        
        # Test retry endpoint
        self.client.force_login(self.developer)
        response = self.client.post(
            f"{reverse('core:retry_distribution')}?id={distribution.id}"
        )
        assert response.status_code == 200
        assert response.json()['success'] is True
        
        # Check distribution was updated
        distribution.refresh_from_db()
        assert distribution.status == 'COMPLETED'
        assert distribution.error_message == ""

    def test_concurrent_distributions(self):
        """Test handling of concurrent distribution processing"""
        # Create multiple revenue records
        revenue2 = Revenue.objects.create(
            app=self.app,
            amount=Decimal("500.00"),
            period_start=timezone.now().replace(day=1),
            period_end=timezone.now()
        )
        
        # Process distributions concurrently
        result1 = self.distribution_service.process_distribution(self.revenue.id)
        result2 = self.distribution_service.process_distribution(revenue2.id)
        
        assert result1 is True
        assert result2 is True
        
        # Verify all distributions were processed correctly
        assert Distribution.objects.filter(
            status=Distribution.Status.COMPLETED
        ).count() == 4  # 2 distributions per revenue

    def test_zero_share_distribution(self):
        """Test distribution when a user has zero shares"""
        # Create user with no shares
        no_shares_user = ShareOwnership.objects.create(
            user=self.regular_user,
            app=self.app,
            shares_owned=0
        )
        
        # Calculate distribution
        distribution = self.distribution_service.calculate_share_distribution(
            self.app, 
            Decimal("1000.00")
        )
        
        # Verify user with zero shares gets no distribution
        zero_share_dist = next(
            (d for d in distribution if d['recipient'] == self.regular_user),
            None
        )
        assert zero_share_dist is None or zero_share_dist['amount'] == Decimal('0')

    def test_distribution_notifications(self):
        """Test distribution notification creation"""
        # Process distribution
        self.distribution_service.process_distribution(self.revenue.id)
        
        # Check notifications were created
        notifications = Notification.objects.filter(
            type='DIVIDEND',
            user=self.investor
        )
        assert notifications.exists()
        
        notification = notifications.first()
        assert str(self.revenue.amount) in notification.message
        assert self.app.name in notification.message

    def test_distribution_rollback(self):
        """Test transaction rollback on distribution failure"""
        # Create a revenue record
        revenue = Revenue.objects.create(
            app=self.app,
            amount=Decimal("1000.00"),
            period_start=timezone.now().replace(day=1),
            period_end=timezone.now()
        )
        
        # Force an error during distribution
        with pytest.raises(Exception):
            with pytest.mock.patch.object(
                self.distribution_service,
                '_process_single_distribution',
                side_effect=Exception("Forced error")
            ):
                self.distribution_service.process_distribution(revenue.id)
        
        # Verify revenue was not marked as distributed
        revenue.refresh_from_db()
        assert revenue.is_distributed is False
        
        # Verify distributions were marked as failed
        failed_distributions = Distribution.objects.filter(
            revenue=revenue,
            status=Distribution.Status.FAILED
        )
        assert failed_distributions.exists()
        assert "Forced error" in failed_distributions.first().error_message

    def test_schedule_distributions(self):
        """Test scheduling of pending distributions"""
        # Create multiple pending revenues
        Revenue.objects.create(
            app=self.app,
            amount=Decimal("500.00"),
            period_start=timezone.now() - timezone.timedelta(days=2),
            period_end=timezone.now() - timezone.timedelta(days=1)
        )
        Revenue.objects.create(
            app=self.app,
            amount=Decimal("750.00"),
            period_start=timezone.now() - timezone.timedelta(days=3),
            period_end=timezone.now() - timezone.timedelta(days=2)
        )
        
        # Schedule distributions
        self.distribution_service.schedule_distributions()
        
        # Verify all distributions were processed
        assert not Revenue.objects.filter(is_distributed=False).exists()
        assert Distribution.objects.filter(
            status=Distribution.Status.COMPLETED
        ).count() == 6  # 2 recipients × 3 revenues

    def test_revenue_distribution(self):
        """Test basic revenue distribution"""
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

class RevenueRecordingTests(TestCase):
    def setUp(self):
        # Create test user
        self.client = Client()
        self.user = User.objects.create_user(
            username='testdev',
            email='test@example.com',
            password='testpass123',
            role='DEVELOPER'
        )
        
        # Create test app
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            ai_features='Test AI Features',
            developer=self.user,
            funding_goal=Decimal('1000000.00'),
            available_percentage=Decimal('20.00'),
            remaining_percentage=Decimal('20.00'),
            price_per_percentage=Decimal('50000.00'),
            equity_percentage=Decimal('100.00'),
            currency='NGN',
            exchange_rate=Decimal('1.0'),
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Log in the user
        self.client.login(username='testdev', password='testpass123')
        
    def test_record_revenue(self):
        """Test recording revenue for an app"""
        url = reverse('core:submit_app_revenue', args=[self.app.id])
        
        # Prepare test data
        today = timezone.now().date()
        data = {
            'amount': 5000.00,
            'source': 'ONE_TIME',
            'description': 'Test revenue',
            'period_start': today.strftime('%Y-%m-%d'),
            'period_end': (today + timezone.timedelta(days=1)).strftime('%Y-%m-%d')  # End date is tomorrow
        }
        
        # Make the request
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Print response details for debugging
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify revenue was created
        revenue = Revenue.objects.filter(app=self.app).first()
        self.assertIsNotNone(revenue)
        self.assertEqual(revenue.amount, Decimal('5000.00'))
        self.assertEqual(revenue.source, 'ONE_TIME')
        self.assertEqual(revenue.currency, 'NGN')
        
    def test_record_revenue_invalid_data(self):
        """Test recording revenue with invalid data"""
        url = reverse('core:submit_app_revenue', args=[self.app.id])
        
        # Test with missing required fields
        data = {
            'amount': 5000.00
            # missing source
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        print(f"Invalid data response: {response.content.decode()}")
        self.assertEqual(response.status_code, 400)
        
    def test_record_revenue_unauthorized(self):
        """Test recording revenue without authorization"""
        # Create another user
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='other123',
            role='DEVELOPER'
        )
        
        # Login as other user
        self.client.login(username='other', password='other123')
        
        url = reverse('core:submit_app_revenue', args=[self.app.id])
        data = {
            'amount': 5000.00,
            'source': 'ONE_TIME',
            'description': 'Test revenue',
            'period_start': timezone.now().strftime('%Y-%m-%d'),
            'period_end': (timezone.now() + timezone.timedelta(days=1)).strftime('%Y-%m-%d')
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        print(f"Unauthorized response: {response.content.decode()}")
        self.assertEqual(response.status_code, 403)  # Should get 403 Forbidden as user is not the app developer
import pytest
from django.urls import reverse
from rest_framework import status
from core.models import AppListing, Investment, AppInsight
from core.api.serializers import AppListingSerializer
from django.utils import timezone

@pytest.mark.django_db
class TestAppInsightViewSet:
    @pytest.fixture(autouse=True)
    def setup(self, client, developer_user):
        self.client = client
        self.user = developer_user
        self.client.force_login(self.user)
        
        # Create test app
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            developer=self.user,
            funding_goal=1000.00,
            share_price=10.00,
            total_shares=100,
            equity_percentage=10.00,
            exchange_rate=750.00,
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Create test insight
        self.insight = AppInsight.objects.create(
            app=self.app,
            insight_type='VALUATION',
            value=50000.00,
            confidence=0.85
        )
    
    def test_list_insights(self):
        """Test listing app insights"""
        url = reverse('core:app-insights-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_insight(self):
        """Test retrieving specific app insight"""
        url = reverse('core:app-insights-detail', kwargs={'pk': self.insight.pk})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
    def test_create_insight(self):
        """Test creating app insight"""
        url = reverse('core:app-insights-list')
        data = {
            'app': self.app.pk,
            'insight_type': 'RISK',
            'value': 0.25,
            'confidence': 0.90
        }
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        
    def test_update_insight(self):
        """Test updating app insight"""
        url = reverse('core:app-insights-detail', kwargs={'pk': self.insight.pk})
        data = {
            'insight_type': 'RISK',
            'value': 0.25,
            'confidence': 0.90
        }
        response = self.client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK 
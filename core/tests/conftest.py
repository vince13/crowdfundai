import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

@pytest.fixture
def client():
    return Client()

@pytest.fixture
def create_user():
    def _create_user(email="test@example.com", password="testpass123", role="INVESTOR"):
        username = email.split('@')[0]  # Use part of email as username
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            is_active=True
        )
    return _create_user

@pytest.fixture
def admin_user(create_user):
    user = create_user(
        email="admin@example.com",
        password="testpass123",
        role="ADMIN"
    )
    user.is_staff = True
    user.save()
    return user

@pytest.fixture
def regular_user(create_user):
    return create_user(
        email="user@example.com",
        password="testpass123",
        role="INVESTOR"
    )

@pytest.fixture
def developer_user(create_user):
    return create_user(
        email="developer@example.com",
        password="testpass123",
        role="DEVELOPER"
    )

@pytest.fixture
def app_listing(developer):
    """Create a test app listing"""
    return AppListing.objects.create(
        name="Test App",
        description="A test app",
        developer=developer,
        funding_goal=Decimal("10000.00"),
        currency='NGN',
        exchange_rate=Decimal("750.00"),
        price_per_percentage=Decimal("500.00"),
        available_percentage=Decimal("20.00"),
        equity_percentage=Decimal("100.00"),
        min_investment_percentage=Decimal("1.00"),
        funding_end_date=timezone.now() + timezone.timedelta(days=30)
    ) 
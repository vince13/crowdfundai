# Test package initialization
from django.contrib.auth import get_user_model

User = get_user_model()

def create_test_user(email="test@example.com", password="testpass123", role="INVESTOR"):
    """Helper function to create test users"""
    username = email.split('@')[0]  # Use part of email as username
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=role,
        is_active=True
    ) 
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from . import create_test_user
from django.conf import settings

class SecurityFeaturesTests(TestCase):
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.admin_user = create_test_user(
            email="admin@example.com",
            password="testpass123",
            role="ADMIN"
        )
        self.admin_user.is_staff = True
        self.admin_user.save()
        
        self.regular_user = create_test_user(
            email="user@example.com",
            password="testpass123",
            role="INVESTOR"
        )
        
        # Clear cache before each test
        cache.clear()

    def test_authentication_required(self):
        """Test authentication requirements for protected views"""
        protected_urls = [
            reverse('core:dashboard'),
            reverse('core:portfolio'),
            reverse('core:transaction_history'),
            reverse('core:analytics_dashboard')
        ]
        
        # Test unauthenticated access
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Should redirect to login
            self.assertIn('login', response.url)
        
        # Test authenticated access
        self.client.force_login(self.regular_user)
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_admin_required_views(self):
        """Test admin-only view protection"""
        admin_urls = [
            reverse('core:admin_dashboard'),
            reverse('core:admin_manage_users'),
            reverse('core:moderation_dashboard')
        ]
        
        # Test regular user access
        self.client.force_login(self.regular_user)
        for url in admin_urls:
            response = self.client.get(url)
            self.assertNotEqual(response.status_code, 200)  # Should not allow access
        
        # Test admin access
        self.client.force_login(self.admin_user)
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)  # Should allow access

    def test_csrf_protection(self):
        """Test CSRF protection."""
        # Create a test user
        user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Log in
        self.client.login(username='testuser', password='testpass123')
        
        # Try to make a POST request without CSRF token
        response = self.client.post(reverse('core:login'), {
            'username': 'testuser',
            'password': 'testpass123'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')  # Make it an AJAX request
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_password_validation(self):
        """Test password validation rules"""
        User = get_user_model()
        
        # Test too short password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="short"  # Too short password
            )
        
        # Test common password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="password123"  # Common password
            )
        
        # Test numeric-only password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="12345678"  # Numeric-only password
            )

    def test_rate_limiting(self):
        """Test rate limiting on sensitive endpoints."""
        # Create a test user
        user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Try to make multiple rapid requests
        for _ in range(10):  # Adjust based on your rate limit settings
            response = self.client.post(reverse('core:login'), {
                'username': 'testuser',
                'password': 'wrong_password'
            })
            
        # The last request should be rate limited
        self.assertEqual(response.status_code, 429)  # Too Many Requests

    def test_secure_headers(self):
        """Test security-related HTTP headers."""
        response = self.client.get(reverse('core:home'))
        
        # Check security headers
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('Referrer-Policy'), 'same-origin')
        
        # In production, should have additional headers
        if not settings.DEBUG:
            self.assertEqual(response.headers.get('Strict-Transport-Security'), 'max-age=31536000; includeSubDomains')
            self.assertEqual(response.headers.get('Content-Security-Policy'), "default-src 'self'")

    def test_session_security(self):
        """Test session security features."""
        # Create a test user
        user = get_user_model().objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Log in
        self.client.login(username='testuser', password='testpass123')
        
        # Make a request to get session cookie
        response = self.client.get(reverse('core:home'))
        
        # Get session cookie
        session_cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        
        # Check session cookie settings
        self.assertIsNotNone(session_cookie)
        self.assertEqual(session_cookie['httponly'], True)  # Should be HttpOnly
        self.assertEqual(session_cookie['samesite'], 'Lax')  # Should be SameSite=Lax
        
        # In production, should be secure
        if not settings.DEBUG:
            self.assertEqual(session_cookie['secure'], True)

    def test_password_validation(self):
        """Test password validation rules"""
        User = get_user_model()
        
        # Test too short password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="short"  # Too short password
            )
        
        # Test common password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="password123"  # Common password
            )
        
        # Test numeric-only password
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="test@example.com",
                password="12345678"  # Numeric-only password
            )

    def test_rate_limiting(self):
        """Test rate limiting on sensitive endpoints"""
        login_url = reverse('core:login')
        
        # Make multiple rapid login attempts
        for _ in range(10):
            response = self.client.post(login_url, {
                'email': 'nonexistent@example.com',
                'password': 'wrongpassword'
            })
        
        # Next attempt should be rate limited
        response = self.client.post(login_url, {
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 429)  # Too Many Requests

    def test_secure_headers(self):
        """Test security-related HTTP headers"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('core:dashboard'))
        
        # Check security headers
        self.assertIn('X-Frame-Options', response.headers)
        self.assertIn('X-Content-Type-Options', response.headers)
        self.assertIn('X-XSS-Protection', response.headers)
        
        # Verify header values
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-XSS-Protection'], '1; mode=block')

    def test_session_security(self):
        """Test session security features"""
        self.client.force_login(self.regular_user)
        
        # Get session cookie
        session_cookie = self.client.cookies.get('sessionid')
        
        # Verify session cookie attributes
        self.assertTrue(session_cookie.secure)  # Should be secure in production
        self.assertTrue(session_cookie.httponly)  # Should be HttpOnly
        
        # Test session timeout
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Simulate session timeout by clearing session
        self.client.session.flush()
        
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login 
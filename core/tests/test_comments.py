from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from ..models import AppListing, AppComment
from decimal import Decimal
import json

User = get_user_model()

class CommentTests(TestCase):
    def setUp(self):
        # Create test users
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='testuser@example.com'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com',
            is_staff=True,
            is_superuser=True
        )
        
        # Create minimal test app in database
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            developer=self.user,
            status='ACTIVE',
            funding_goal=Decimal('1000.00'),
            currency='NGN',
            exchange_rate=Decimal('1.00'),
            available_percentage=Decimal('100.00'),
            min_investment=Decimal('100.00'),
            max_investment=Decimal('1000.00'),
            total_equity_offered=Decimal('20.00'),
            current_valuation=Decimal('5000.00'),
            listing_type='STANDARD',
            development_stage='CONCEPT',
            category='OTHER',
            deployment_type='SAAS',
            revenue_model='SUBSCRIPTION'
        )
        
        # Create test comment
        self.comment = AppComment.objects.create(
            app=self.app,
            user=self.user,
            content='Test comment'
        )

    def test_get_comments(self):
        """Test getting comments returns correct data structure"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:get_comments', args=[self.app.id]))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('comments', data)
        
        if data['comments']:  # Only test if there are comments
            comment = data['comments'][0]
            # Check required fields exist and have correct values
            self.assertEqual(comment['app_id'], self.app.id)
            self.assertIsNotNone(comment['can_delete'])
            self.assertIsNotNone(comment['is_author'])
            self.assertEqual(comment['author_name'], self.user.username)
            self.assertEqual(comment['content'], 'Test comment')

    def test_add_comment(self):
        """Test adding a comment returns correct data"""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('core:add_comment', args=[self.app.id]),
            data=json.dumps({'content': 'New comment'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        comment = data['comment']
        # Check required fields exist and have correct values
        self.assertEqual(comment['app_id'], self.app.id)
        self.assertIsNotNone(comment['can_delete'])
        self.assertTrue(comment['is_author'])  # User should be author of their own comment
        self.assertEqual(comment['author_name'], self.user.username)

    def test_delete_comment(self):
        """Test comment deletion permissions"""
        # Test owner can delete
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('core:delete_comment', args=[self.app.id, self.comment.id])
        )
        self.assertEqual(response.status_code, 200)
        
        # Test admin can delete
        comment = AppComment.objects.create(
            app=self.app,
            user=self.user,
            content='Test'
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('core:delete_comment', args=[self.app.id, comment.id])
        )
        self.assertEqual(response.status_code, 200)
        
        # Test other users cannot delete
        other_user = User.objects.create_user(
            username='other',
            password='pass123',
            email='other@example.com'
        )
        self.client.force_login(other_user)
        comment = AppComment.objects.create(
            app=self.app,
            user=self.user,
            content='Test'
        )
        response = self.client.post(
            reverse('core:delete_comment', args=[self.app.id, comment.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_report_comment(self):
        """Test comment reporting"""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('core:report_comment', args=[self.app.id, self.comment.id]),
            data=json.dumps({'reason': 'inappropriate content'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success']) 
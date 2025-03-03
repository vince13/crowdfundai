from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from ..models import User, AppListing, EscrowTransaction, ProjectMilestone
from ..services.escrow import EscrowService
from django.core.exceptions import ValidationError
import json
from datetime import datetime, timedelta
from django.db import models

class EscrowSystemTests(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@example.com',
            password='testpass123',
            role=User.Role.DEVELOPER
        )
        self.investor = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='testpass123',
            role=User.Role.INVESTOR
        )
        
        # Create test app listing
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            ai_features='Test AI Features',
            developer=self.developer,
            funding_goal=Decimal('10000.00'),
            currency='NGN',
            exchange_rate=Decimal('1.0000'),
            available_percentage=Decimal('20.00'),
            min_investment_percentage=Decimal('1.00'),
            equity_percentage=Decimal('20.00'),
            remaining_percentage=Decimal('20.00'),
            price_per_percentage=Decimal('500.00'),
            funding_round='PRESEED',
            round_number=1,
            lock_in_period=180,
            funding_end_date=timezone.now() + timezone.timedelta(days=30),
            use_of_funds={'development': 100}
        )
        
        # Create test milestone
        self.milestone = ProjectMilestone.objects.create(
            app=self.app,
            title='Test Milestone',
            description='Test Description',
            target_date=timezone.now().date() + timezone.timedelta(days=30),
            release_percentage=Decimal('25.00')
        )

    def test_deposit_to_escrow(self):
        """Test depositing funds to escrow."""
        amount = Decimal('1000.00')
        
        escrow_tx = EscrowService.process_deposit(
            app=self.app,
            investor=self.investor,
            amount=amount,
            currency='USD',
            payment_gateway='STRIPE',
            gateway_reference='test_ref_123'
        )
        
        self.assertEqual(escrow_tx.status, 'COMPLETED')
        self.assertEqual(escrow_tx.amount, amount)
        self.assertEqual(self.app.funds_in_escrow, amount)

    def test_milestone_release(self):
        """Test milestone-based release of funds."""
        # First deposit funds
        deposit_amount = Decimal('1000.00')
        deposit = EscrowService.process_deposit(
            app=self.app,
            investor=self.investor,
            amount=deposit_amount,
            currency='USD',
            payment_gateway='STRIPE',
            gateway_reference='test_ref_123'
        )
        
        # Complete milestone
        self.milestone.status = 'COMPLETED'
        self.milestone.save()
        
        # Process release
        release = EscrowService.process_release(
            escrow_tx=deposit,
            milestone=self.milestone,
            release_percentage=self.milestone.release_percentage
        )
        
        expected_release = Decimal('250.00')  # 25% of 1000
        self.assertEqual(release.amount, expected_release)
        self.assertEqual(self.app.funds_in_escrow, deposit_amount - expected_release)

    def test_dispute_handling(self):
        """Test dispute handling process."""
        # Create initial deposit
        deposit = EscrowService.process_deposit(
            app=self.app,
            investor=self.investor,
            amount=Decimal('1000.00'),
            currency='USD',
            payment_gateway='STRIPE',
            gateway_reference='test_ref_123'
        )
        
        # Initiate dispute
        deposit.initiate_dispute("Test dispute reason")
        self.assertEqual(deposit.dispute_status, 'PENDING')
        self.assertEqual(deposit.status, 'DISPUTED')
        
        # Resolve dispute with refund
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        deposit.resolve_dispute(
            resolver=admin_user,
            resolution_type='RESOLVED_REFUND',
            notes="Test resolution notes"
        )
        
        # Check refund was created
        refund = EscrowTransaction.objects.get(
            original_transaction=deposit,
            transaction_type='REFUND'
        )
        self.assertEqual(refund.amount, deposit.amount)
        self.assertEqual(self.app.funds_in_escrow, Decimal('0.00'))

    def test_batch_release(self):
        """Test batch release of funds for multiple deposits."""
        # Create multiple deposits
        deposits = []
        total_amount = Decimal('0.00')
        
        for i in range(3):
            amount = Decimal('1000.00')
            deposit = EscrowService.process_deposit(
                app=self.app,
                investor=self.investor,
                amount=amount,
                currency='USD',
                payment_gateway='STRIPE',
                gateway_reference=f'test_ref_{i}'
            )
            deposits.append(deposit)
            total_amount += amount
        
        # Complete milestone and process batch release
        self.milestone.status = 'COMPLETED'
        self.milestone.save()
        
        result = self.milestone.process_batch_release()
        
        expected_release = total_amount * self.milestone.release_percentage / Decimal('100.0')
        self.assertEqual(result['success_count'], 3)
        self.assertEqual(result['failed_count'], 0)
        self.assertEqual(result['total_released'], expected_release)
        self.assertEqual(
            self.app.funds_in_escrow,
            total_amount - expected_release
        )

    def test_rollback_functionality(self):
        """Test transaction rollback functionality"""
        # Create a refund that would exceed available funds
        with self.assertRaises(ValueError):
            EscrowTransaction.objects.create(
                app=self.app,
                investor=self.investor,
                transaction_type=EscrowTransaction.Type.REFUND,
                amount=Decimal('2000.00'),  # More than available
                currency='NGN',
                payment_gateway='PAYSTACK',
                gateway_reference='test_invalid_refund',
                refund_reason='Invalid refund attempt - insufficient funds'  # Updated refund reason
            )
        
        # Verify the escrow balance remains unchanged
        self.assertEqual(self.app.funds_in_escrow, Decimal('1000.00'))

    def test_fund_validation(self):
        """Test fund validation logic."""
        # Try to release more than available
        deposit = EscrowService.process_deposit(
            app=self.app,
            investor=self.investor,
            amount=Decimal('1000.00'),
            currency='USD',
            payment_gateway='STRIPE',
            gateway_reference='test_ref_123'
        )
        
        with self.assertRaises(ValueError):
            EscrowService.process_release(
                escrow_tx=deposit,
                release_percentage=Decimal('150.00')  # Try to release 150%
            )

    def test_escrow_summary(self):
        """Test escrow balance summary"""
        # Create additional transactions
        EscrowTransaction.objects.create(
            app=self.app,
            investor=self.investor,
            transaction_type=EscrowTransaction.Type.DEPOSIT,
            amount=Decimal('500.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='test_deposit_2'
        )
        
        refund = EscrowTransaction.objects.create(
            app=self.app,
            investor=self.investor,
            transaction_type=EscrowTransaction.Type.REFUND,
            amount=Decimal('200.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='test_refund_2',
            refund_reason='Project scope reduced - partial refund issued'  # Updated refund reason
        )
        
        self.assertIsNotNone(refund.refund_reason)  # Verify refund reason is set
        
        # Calculate expected balance
        deposits = EscrowTransaction.objects.filter(
            app=self.app,
            transaction_type=EscrowTransaction.Type.DEPOSIT
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        refunds = EscrowTransaction.objects.filter(
            app=self.app,
            transaction_type__in=[
                EscrowTransaction.Type.REFUND,
                EscrowTransaction.Type.PARTIAL_REFUND
            ]
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        expected_balance = deposits - refunds
        self.assertEqual(self.app.funds_in_escrow, expected_balance)

    def test_refund(self):
        """Test refunding funds to investor"""
        refund = EscrowTransaction.objects.create(
            app=self.app,
            investor=self.investor,
            transaction_type=EscrowTransaction.Type.REFUND,
            amount=Decimal('1000.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='test_refund_123',
            refund_reason='Project cancelled - funds returned to investor'  # Added detailed refund reason
        )
        
        self.assertEqual(refund.status, 'PENDING')
        self.assertEqual(self.app.funds_in_escrow, Decimal('0.00'))
        self.assertIsNotNone(refund.refund_reason)  # Verify refund reason is set

    def test_partial_refund(self):
        """Test partial refund of funds"""
        partial_refund = EscrowTransaction.objects.create(
            app=self.app,
            investor=self.investor,
            transaction_type=EscrowTransaction.Type.PARTIAL_REFUND,
            amount=Decimal('500.00'),
            currency='NGN',
            payment_gateway='PAYSTACK',
            gateway_reference='test_partial_refund_123',
            refund_reason='Milestone cancelled - partial refund issued'  # Added detailed refund reason
        )
        
        self.assertEqual(partial_refund.status, 'PENDING')
        self.assertEqual(self.app.funds_in_escrow, Decimal('500.00'))
        self.assertIsNotNone(partial_refund.refund_reason)  # Verify refund reason is set

    def test_dispute_handling(self):
        """Test handling of disputes"""
        # Initiate dispute
        self.deposit.initiate_dispute('Funds not properly allocated')
        self.assertEqual(self.deposit.dispute_status, 'PENDING')
        self.assertEqual(self.deposit.status, 'DISPUTED')
        
        # Resolve dispute with refund
        self.deposit.resolve_dispute(
            resolver=self.developer,
            resolution_type=EscrowTransaction.DisputeStatus.RESOLVED_REFUND,
            notes='Dispute resolved in favor of investor'
        )
        
        # Check that a refund transaction was created
        refund = EscrowTransaction.objects.filter(
            transaction_type=EscrowTransaction.Type.REFUND,
            original_transaction=self.deposit
        ).first()
        
        self.assertIsNotNone(refund)
        self.assertEqual(refund.refund_reason, 'Dispute resolved in favor of refund')

    def test_rollback_functionality(self):
        """Test transaction rollback functionality"""
        # Create a refund that would exceed available funds
        with self.assertRaises(ValueError):
            EscrowTransaction.objects.create(
                app=self.app,
                investor=self.investor,
                transaction_type=EscrowTransaction.Type.REFUND,
                amount=Decimal('2000.00'),  # More than available
                currency='NGN',
                payment_gateway='PAYSTACK',
                gateway_reference='test_invalid_refund',
                refund_reason='Invalid refund attempt - insufficient funds'  # Updated refund reason
            )
        
        # Verify the escrow balance remains unchanged
        self.assertEqual(self.app.funds_in_escrow, Decimal('1000.00')) 
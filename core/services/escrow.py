from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from ..models import EscrowTransaction, AppListing
import logging

logger = logging.getLogger(__name__)

class EscrowService:
    @staticmethod
    def calculate_release_amount(base_amount: Decimal, percentage: Decimal) -> Decimal:
        """Calculate release amount based on percentage."""
        if not isinstance(base_amount, Decimal):
            base_amount = Decimal(str(base_amount))
        if not isinstance(percentage, Decimal):
            percentage = Decimal(str(percentage))
            
        return (base_amount * percentage / Decimal('100.0')).quantize(Decimal('0.01'))

    @staticmethod
    def validate_funds(app: AppListing, amount: Decimal) -> bool:
        """Validate if sufficient funds are available in escrow."""
        return app.funds_in_escrow >= amount

    @staticmethod
    def process_deposit(app: AppListing, investor, amount: Decimal, currency: str, 
                       payment_gateway: str, gateway_reference: str) -> EscrowTransaction:
        """Process a new deposit to escrow."""
        with transaction.atomic():
            escrow_tx = EscrowTransaction.objects.create(
                app=app,
                investor=investor,
                transaction_type='DEPOSIT',
                amount=amount,
                currency=currency,
                payment_gateway=payment_gateway,
                gateway_reference=gateway_reference,
                status='COMPLETED',
                completed_at=timezone.now()
            )
            
            app.funds_in_escrow += amount
            app.save()
            
            return escrow_tx

    @staticmethod
    def process_release(escrow_tx: EscrowTransaction, milestone=None, 
                       release_percentage: Decimal = None) -> EscrowTransaction:
        """Process a release from escrow."""
        with transaction.atomic():
            release_amount = escrow_tx.amount
            if release_percentage:
                release_amount = EscrowService.calculate_release_amount(
                    escrow_tx.amount, release_percentage
                )
                
            if not EscrowService.validate_funds(escrow_tx.app, release_amount):
                raise ValueError("Insufficient funds in escrow")
                
            release = EscrowTransaction.objects.create(
                app=escrow_tx.app,
                investor=escrow_tx.investor,
                transaction_type='MILESTONE_RELEASE' if milestone else 'RELEASE',
                amount=release_amount,
                currency=escrow_tx.currency,
                payment_gateway=escrow_tx.payment_gateway,
                gateway_reference=f"{escrow_tx.gateway_reference}_release",
                milestone=milestone,
                release_percentage=release_percentage,
                original_transaction=escrow_tx,
                status='COMPLETED',
                completed_at=timezone.now()
            )
            
            escrow_tx.app.funds_in_escrow -= release_amount
            escrow_tx.app.save()
            
            return release

    @staticmethod
    def process_refund(escrow_tx: EscrowTransaction, reason: str = None, 
                      refund_percentage: Decimal = None) -> EscrowTransaction:
        """Process a refund from escrow."""
        with transaction.atomic():
            refund_amount = escrow_tx.amount
            if refund_percentage:
                refund_amount = EscrowService.calculate_release_amount(
                    escrow_tx.amount, refund_percentage
                )
                
            if not EscrowService.validate_funds(escrow_tx.app, refund_amount):
                raise ValueError("Insufficient funds in escrow")
                
            refund = EscrowTransaction.objects.create(
                app=escrow_tx.app,
                investor=escrow_tx.investor,
                transaction_type='PARTIAL_REFUND' if refund_percentage else 'REFUND',
                amount=refund_amount,
                currency=escrow_tx.currency,
                payment_gateway=escrow_tx.payment_gateway,
                gateway_reference=f"{escrow_tx.gateway_reference}_refund",
                original_transaction=escrow_tx,
                refund_reason=reason,
                status='COMPLETED',
                completed_at=timezone.now()
            )
            
            escrow_tx.app.funds_in_escrow -= refund_amount
            escrow_tx.app.save()
            
            return refund

    @staticmethod
    def get_escrow_summary(app: AppListing) -> dict:
        """Get a summary of escrow transactions for an app."""
        deposits = EscrowTransaction.objects.filter(
            app=app,
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        releases = EscrowTransaction.objects.filter(
            app=app,
            transaction_type__in=['RELEASE', 'MILESTONE_RELEASE'],
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        refunds = EscrowTransaction.objects.filter(
            app=app,
            transaction_type__in=['REFUND', 'PARTIAL_REFUND'],
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        disputes = EscrowTransaction.objects.filter(
            app=app,
            dispute_status='PENDING'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_deposits': deposits,
            'total_releases': releases,
            'total_refunds': refunds,
            'funds_in_dispute': disputes,
            'available_balance': app.funds_in_escrow - disputes
        } 
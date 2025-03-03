import logging
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.mail import send_mail
from .base import Transaction, EscrowTransaction

logger = logging.getLogger(__name__)

class EscrowRelease(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='escrow_releases')
    milestone = models.ForeignKey('ProjectMilestone', on_delete=models.CASCADE, related_name='escrow_releases')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    requested_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='requested_releases')
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='approved_releases')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    transaction_reference = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Release for {self.milestone.title} - {self.get_status_display()}"

    def approve(self, admin_user, notes=''):
        """Approve the escrow release request."""
        logger.info(f"Starting approval process for release {self.id} by admin {admin_user.email}")
        
        if self.status == self.Status.PENDING:
            logger.info(f"Release {self.id} is in PENDING status, proceeding with approval")
            self.status = self.Status.APPROVED
            self.approved_by = admin_user
            self.notes = notes
            self.save()

            # Process the actual fund transfer
            try:
                logger.info(f"Attempting to process transfer for release {self.id}")
                transaction = self.process_transfer()
                logger.info(f"Transfer processed successfully, transaction ID: {transaction.id}")
                
                self.transaction_reference = str(transaction.id)
                self.status = self.Status.COMPLETED
                self.completed_at = timezone.now()
                self.save()
                
                # Create EscrowTransaction record
                logger.info(f"Creating EscrowTransaction record for release {self.id}")
                escrow_tx = EscrowTransaction.objects.create(
                    app=self.app,
                    investor=self.app.developer,  # Developer is the recipient
                    transaction_type=EscrowTransaction.Type.MILESTONE_RELEASE,
                    amount=self.amount,  # Use full amount without fee
                    currency='NGN',  # Set appropriate currency
                    payment_gateway='PAYSTACK',  # Set appropriate gateway
                    gateway_reference=str(transaction.id),
                    status='COMPLETED',
                    milestone=self.milestone,
                    completed_at=timezone.now()
                )
                logger.info(f"Created EscrowTransaction {escrow_tx.id} for release {self.id}")

                # Update app's funds in escrow
                self.app.funds_in_escrow -= self.amount
                self.app.save()

                # Send email notification to developer
                send_mail(
                    f'Funds Released: {self.milestone.title}',
                    f'₦{self.amount:,.2f} has been released to your account.',
                    'noreply@example.com',
                    [self.app.developer.email],
                    fail_silently=True,
                )
                
                logger.info(f"Release {self.id} completed successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to process release {self.id}: {str(e)}")
                self.status = self.Status.FAILED
                self.notes = f"{self.notes}\nTransfer failed: {str(e)}"
                self.save()
                return False
        else:
            logger.warning(f"Cannot approve release {self.id}: current status is {self.status}")
        return False

    def reject(self, admin_user, notes):
        """Reject the escrow release request."""
        logger.info(f"Starting rejection process for release {self.id} by admin {admin_user.email}")
        
        if self.status == self.Status.PENDING:
            logger.info(f"Release {self.id} is in PENDING status, proceeding with rejection")
            self.status = self.Status.REJECTED
            self.approved_by = admin_user
            self.notes = notes
            self.save()

            # Send email notification to developer
            send_mail(
                f'Fund Release Rejected: {self.milestone.title}',
                f'Fund release request was rejected. Notes: {notes}',
                'noreply@example.com',
                [self.app.developer.email],
                fail_silently=True,
            )
            
            logger.info(f"Release {self.id} rejected successfully")
            return True
        else:
            logger.warning(f"Cannot reject release {self.id}: current status is {self.status}")
        return False

    def process_transfer(self):
        """Process the actual fund transfer."""
        logger.info(f"Processing transfer for release {self.id}, amount: {self.amount}")
        
        try:
            transaction = Transaction.objects.create(
            user=self.app.developer,
            app=self.app,
            amount=self.amount,
            transaction_type=Transaction.Type.REVENUE
        ) 
            logger.info(f"Created revenue transaction {transaction.id} for release {self.id}")
            return transaction
        except Exception as e:
            logger.error(f"Failed to create transaction for release {self.id}: {str(e)}")
            raise 

    def retry(self, admin_user, notes=''):
        """Retry a failed release."""
        logger.info(f"Starting retry process for release {self.id} by admin {admin_user.email}")
        
        if self.status == self.Status.FAILED:
            logger.info(f"Release {self.id} is in FAILED status, proceeding with retry")
            self.status = self.Status.APPROVED
            self.approved_by = admin_user
            if notes:
                self.notes = f"{self.notes}\n\nRetry Notes: {notes}"
            self.save()

            # Process the actual fund transfer
            try:
                logger.info(f"Attempting to process transfer for release {self.id}")
                transaction = self.process_transfer()
                logger.info(f"Transfer processed successfully, transaction ID: {transaction.id}")
                
                self.transaction_reference = str(transaction.id)
                self.status = self.Status.COMPLETED
                self.completed_at = timezone.now()
                self.save()
                
                # Create EscrowTransaction record
                logger.info(f"Creating EscrowTransaction record for release {self.id}")
                escrow_tx = EscrowTransaction.objects.create(
                    app=self.app,
                    investor=self.app.developer,  # Developer is the recipient
                    transaction_type=EscrowTransaction.Type.MILESTONE_RELEASE,
                    amount=self.amount,  # Use full amount without fee
                    currency='NGN',  # Set appropriate currency
                    payment_gateway='PAYSTACK',  # Set appropriate gateway
                    gateway_reference=str(transaction.id),
                    status='COMPLETED',
                    milestone=self.milestone,
                    completed_at=timezone.now()
                )
                logger.info(f"Created EscrowTransaction {escrow_tx.id} for release {self.id}")

                # Send email notification to developer
                send_mail(
                    f'Funds Released Successfully: {self.milestone.title}',
                    f'₦{self.amount:,.2f} has been released to your account after a successful retry.',
                    'noreply@example.com',
                    [self.app.developer.email],
                    fail_silently=True,
                )
                
                logger.info(f"Release {self.id} retry completed successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to process release {self.id} retry: {str(e)}")
                self.status = self.Status.FAILED
                self.notes = f"{self.notes}\nRetry failed: {str(e)}"
                self.save()
                return False
        else:
            logger.warning(f"Cannot retry release {self.id}: current status is {self.status}")
        return False 
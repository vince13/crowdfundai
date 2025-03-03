from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .escrow import EscrowRelease
from .base import AppListing

class ProjectMilestone(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        DELAYED = 'DELAYED', 'Delayed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        VERIFICATION_REQUESTED = 'VERIFICATION_REQUESTED', 'Verification Requested'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected'

    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    release_percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    verification_notes = models.TextField(blank=True)
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_milestones')

    def __str__(self):
        return self.title

    def mark_completed(self):
        """Mark milestone as completed and trigger fund release."""
        if self.status == self.Status.COMPLETED:
            return False
        
        self.status = self.Status.COMPLETED
        self.completion_date = timezone.now().date()
        self.progress = 100
        self.save()

        # Find associated escrow transactions and process releases
        escrow_transactions = self.app.escrowtransaction_set.filter(
            transaction_type='DEPOSIT',
            status='COMPLETED'
        )
        
        for transaction in escrow_transactions:
            transaction.process_milestone_release(self)
        
        return True

    def calculate_remaining_funds(self):
        """Calculate remaining funds to be released for this milestone."""
        total_escrow = self.app.funds_in_escrow
        allocated_amount = (total_escrow * self.release_percentage) / Decimal('100.0')
        
        # Calculate already released amount
        released_amount = EscrowRelease.objects.filter(
            milestone=self,
            status__in=['COMPLETED', 'APPROVED']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        return max(Decimal('0'), allocated_amount - released_amount)

    def get_total_released(self):
        """Get total amount released for this milestone."""
        return EscrowRelease.objects.filter(
            milestone=self,
            status__in=['COMPLETED', 'APPROVED']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    def can_request_release(self, amount):
        """Check if the requested amount can be released."""
        if not self.status == self.Status.VERIFIED:
            return False, "Milestone must be verified before requesting release"
            
        remaining = self.calculate_remaining_funds()
        if amount > remaining:
            return False, f"Requested amount (₦{amount}) exceeds remaining funds (₦{remaining})"
            
        return True, "Release request allowed"

    def get_deliverables_status(self):
        """Get a summary of deliverables status."""
        total = self.deliverables.count()
        completed = self.deliverables.filter(status='COMPLETED').count()
        return {
            'total': total,
            'completed': completed,
            'percentage': (completed / total * 100) if total > 0 else 0
        }

    def verify_completion(self):
        """Verify milestone completion with admin approval."""
        if not self.can_release_funds()[0]:
            return False, "Milestone does not meet release criteria"

        # Check if all deliverables are documented and verified
        if not self.deliverables.exists():
            return False, "No deliverables documented for this milestone"

        incomplete_deliverables = self.deliverables.exclude(status='COMPLETED')
        if incomplete_deliverables.exists():
            return False, "Some deliverables are not completed"

        return True, "Milestone ready for completion verification"

    def request_completion_verification(self):
        """Request admin verification for milestone completion."""
        can_complete, message = self.verify_completion()
        if not can_complete:
            raise ValueError(message)

        # Create verification request
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True)
        
        # Notify admins (implement notification system)
        for admin in admins:
            # Create notification for admin
            pass

        return True, "Verification request sent to admins"

    def can_release_funds(self):
        """Check if milestone meets all criteria for fund release."""
        if self.status != self.Status.COMPLETED:
            return False, "Milestone is not completed"
            
        # Verify all deliverables are properly documented
        incomplete_deliverables = self.deliverables.exclude(status='COMPLETED')
        if incomplete_deliverables.exists():
            return False, "Some deliverables are not completed"
            
        # Check if there are any pending disputes
        pending_disputes = self.app.escrowtransaction_set.filter(
            milestone=self,
            dispute_status='PENDING'
        ).exists()
        if pending_disputes:
            return False, "There are pending disputes"
            
        return True, "Ready for fund release"

    def process_batch_release(self):
        """Process releases for multiple transactions in a batch."""
        can_release, message = self.can_release_funds()
        if not can_release:
            raise ValueError(f"Cannot release funds: {message}")
            
        from django.db import transaction
        
        with transaction.atomic():
            escrow_transactions = self.app.escrowtransaction_set.filter(
                transaction_type='DEPOSIT',
                status='COMPLETED'
            ).select_for_update()
            
            success_count = 0
            failed_count = 0
            total_released = Decimal('0.00')
            
            for escrow_tx in escrow_transactions:
                try:
                    release_amount = (escrow_tx.amount * self.release_percentage) / Decimal('100.0')
                    escrow_tx.process_milestone_release(self)
                    success_count += 1
                    total_released += release_amount
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to process release for transaction {escrow_tx.id}: {str(e)}")
            
            return {
                'success_count': success_count,
                'failed_count': failed_count,
                'total_released': total_released
            }

    def rollback_release(self, release_transaction):
        """Rollback a failed milestone release."""
        if release_transaction.transaction_type != 'MILESTONE_RELEASE':
            raise ValueError("Can only rollback milestone release transactions")
            
        from django.db import transaction
        
        with transaction.atomic():
            # Create refund transaction
            refund = EscrowTransaction.objects.create(
                app=release_transaction.app,
                investor=release_transaction.investor,
                transaction_type='REFUND',
                amount=release_transaction.amount,
                currency=release_transaction.currency,
                payment_gateway=release_transaction.payment_gateway,
                gateway_reference=f"ROLLBACK_{release_transaction.gateway_reference}",
                milestone=self,
                original_transaction=release_transaction,
                refund_reason="Milestone release rollback"
            )
            
            # Update app's escrow balance
            self.app.funds_in_escrow += release_transaction.amount
            self.app.save()
            
            # Mark original release as failed
            release_transaction.status = 'FAILED'
            release_transaction.save()
            
            return refund

    def clean(self):
        """Validate milestone changes."""
        super().clean()
        if self.pk:  # Existing milestone
            original = ProjectMilestone.objects.get(pk=self.pk)
            if self.app.status != 'PENDING':
                # Only allow status and progress updates after app is active
                protected_fields = ['title', 'description', 'target_date', 'release_percentage']
                for field in protected_fields:
                    if getattr(self, field) != getattr(original, field):
                        raise ValidationError(f'{field} cannot be modified after app is active')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def request_verification(self):
        """Developer requests milestone verification."""
        if self.progress == 100 and self.status == self.Status.IN_PROGRESS:
            self.status = self.Status.VERIFICATION_REQUESTED
            self.verification_requested_at = timezone.now()
            self.save()
            
            # Notify admins through email instead of notifications
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                # Send email notification to admin
                send_mail(
                    f'Milestone Verification Request: {self.title}',
                    f'App: {self.app.name}\nMilestone: {self.title}\nRequested by: {self.app.developer.username}',
                    'noreply@example.com',
                    [admin.email],
                    fail_silently=True,
                )
            return True
        return False

    def verify(self, admin_user, notes=''):
        """Admin verifies the milestone and triggers fund release."""
        if self.status == self.Status.VERIFICATION_REQUESTED:
            self.status = self.Status.VERIFIED
            self.verified_at = timezone.now()
            self.verified_by = admin_user
            self.verification_notes = notes
            self.completion_date = timezone.now().date()
            self.save()

            # Create escrow release request
            EscrowRelease.objects.create(
                app=self.app,
                milestone=self,
                amount=self.calculate_release_amount(),
                requested_by=admin_user,
                status='PENDING'
            )

            # Send email notification to developer
            from django.core.mail import send_mail
            send_mail(
                f'Milestone Verified: {self.title}',
                f'Your milestone has been verified. Funds will be released shortly.',
                'noreply@example.com',
                [self.app.developer.email],
                fail_silently=True,
            )
            return True
        return False

    def reject(self, admin_user, notes):
        """Admin rejects the milestone verification."""
        if self.status == self.Status.VERIFICATION_REQUESTED:
            self.status = self.Status.IN_PROGRESS
            self.verification_notes = notes
            self.save()

            # Send email notification to developer
            from django.core.mail import send_mail
            send_mail(
                f'Milestone Verification Rejected: {self.title}',
                f'Verification rejected. Notes: {notes}',
                'noreply@example.com',
                [self.app.developer.email],
                fail_silently=True,
            )
            return True
        return False

    def calculate_release_amount(self):
        """Calculate the amount to be released for this milestone."""
        total_funding = self.app.funding_goal
        return (total_funding * self.release_percentage) / Decimal('100.0')

class Deliverable(models.Model):
    class Status(models.TextChoices):
        TODO = 'TODO', 'To Do'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        BLOCKED = 'BLOCKED', 'Blocked'

    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.CASCADE, related_name='deliverables')
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    due_date = models.DateField()
    evidence_file = models.FileField(
        upload_to='deliverables/evidence/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload evidence files (e.g. documents, screenshots, videos)"
    )
    evidence_link = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="External link to evidence (e.g. GitHub repo, demo video)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ProjectUpdate(models.Model):
    class UpdateType(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        MILESTONE = 'MILESTONE', 'Milestone'
        TECHNICAL = 'TECHNICAL', 'Technical'
        BUSINESS = 'BUSINESS', 'Business'
        TEAM = 'TEAM', 'Team'

    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='updates')
    title = models.CharField(max_length=200)
    content = models.TextField()
    update_type = models.CharField(max_length=20, choices=UpdateType.choices, default=UpdateType.GENERAL)
    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.SET_NULL, null=True, blank=True, related_name='updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ProjectTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AppTag(models.Model):
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='tags')
    tag = models.ForeignKey(ProjectTag, on_delete=models.CASCADE, related_name='apps')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('app', 'tag')

class ReleaseRequest(models.Model):
    """Model to track fund release requests from developers."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
    
    milestone = models.ForeignKey('ProjectMilestone', on_delete=models.CASCADE, related_name='release_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Amount requested for release')
    requested_by = models.ForeignKey('User', on_delete=models.CASCADE, related_name='release_requests')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, help_text='Additional notes or context for the request')
    admin_notes = models.TextField(blank=True, help_text='Admin notes on request processing')
    processed_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_releases')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f'Release Request #{self.id} - {self.milestone.title} (₦{self.amount})'
        
    def approve(self, admin_user, notes=''):
        """Approve the release request."""
        if self.status != self.Status.PENDING:
            return False
        self.status = self.Status.APPROVED
        self.processed_by = admin_user
        self.admin_notes = notes
        self.processed_at = timezone.now()
        self.save()
        
        # Create escrow release
        EscrowRelease.objects.create(
            milestone=self.milestone,
            amount=self.amount,
            requested_by=self.requested_by,
            approved_by=admin_user,
            notes=self.notes,
            admin_notes=notes
        )
        return True
        
    def reject(self, admin_user, notes=''):
        """Reject the release request."""
        if self.status != self.Status.PENDING:
            return False
        self.status = self.Status.REJECTED
        self.processed_by = admin_user
        self.admin_notes = notes
        self.processed_at = timezone.now()
        self.save()
        return True 
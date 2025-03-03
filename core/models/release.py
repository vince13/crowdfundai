from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

class Release(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    # Core Fields
    transaction = models.ForeignKey(
        'Transaction', 
        on_delete=models.PROTECT, 
        related_name='releases',
        null=True,
        blank=True
    )
    milestone = models.ForeignKey(
        'ProjectMilestone',
        on_delete=models.PROTECT,
        related_name='releases',
        null=True,
        blank=True
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Request Details
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='releases_requested'
    )
    request_date = models.DateTimeField(auto_now_add=True)
    request_notes = models.TextField(blank=True)
    
    # Approval Request Details
    approval_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_requests_initiated'
    )
    approval_requested_at = models.DateTimeField(null=True, blank=True)
    
    # Approval Details
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='releases_approved'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Rejection Details
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='releases_rejected'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Processing Details
    processed_date = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['request_date']),
            models.Index(fields=['approval_requested_at']),
        ]
        permissions = [
            ("can_approve_release", "Can approve fund releases"),
            ("can_process_release", "Can process fund releases"),
        ]

    def __str__(self):
        return f"Release #{self.id} - {self.amount} ({self.get_status_display()})"

    def clean(self):
        """Validate the release."""
        super().clean()
        
        # Ensure either transaction or milestone is provided
        if not self.transaction and not self.milestone:
            raise ValidationError("Either transaction or milestone must be provided")
        
        if self.transaction and self.milestone:
            raise ValidationError("Cannot specify both transaction and milestone")
            
        # For milestone-based releases, validate milestone status
        if self.milestone:
            if self.milestone.status != 'VERIFIED':
                raise ValidationError("Can only create releases for verified milestones")
            
            # Calculate maximum amount that can be released for this milestone
            max_amount = self.milestone.calculate_release_amount()
            if self.amount > max_amount:
                raise ValidationError(f"Release amount cannot exceed {max_amount}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def app(self):
        """Get the associated app."""
        if self.transaction:
            return self.transaction.app
        return self.milestone.app

    @property
    def developer(self):
        """Get the developer who should receive the funds."""
        return self.app.developer

    def can_request_approval(self):
        """Check if release can have approval requested"""
        return (
            self.status == self.Status.PENDING and
            self.approval_requested_at is None and
            self.approval_date is None and
            self.rejected_at is None
        )

    def can_be_approved(self):
        """Check if release can be approved"""
        return (
            self.status == self.Status.PENDING and
            self.approval_requested_at is not None and
            self.approval_date is None and
            self.rejected_at is None
        )

    def can_be_rejected(self):
        """Check if release can be rejected"""
        return self.can_be_approved()

    def approve(self, approved_by, notes=''):
        """Approve a release request."""
        if not self.can_be_approved():
            raise ValueError("Release cannot be approved in current state")
        
        self.status = self.Status.APPROVED
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.save()

    def reject(self, rejected_by, reason):
        """Reject a release request."""
        if not self.can_be_rejected():
            raise ValueError("Release cannot be rejected in current state")
        
        self.status = self.Status.REJECTED
        self.rejected_by = rejected_by
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def mark_processing(self):
        """Mark release as processing."""
        if self.status != self.Status.APPROVED:
            raise ValueError("Only approved releases can be processed")
        
        self.status = self.Status.PROCESSING
        self.processed_date = timezone.now()
        self.save()

    def complete(self, reference=''):
        """Mark release as completed."""
        if self.status != self.Status.PROCESSING:
            raise ValueError("Only processing releases can be completed")
        
        self.status = self.Status.COMPLETED
        self.reference = reference
        self.save()

    def fail(self, reason=''):
        """Mark release as failed."""
        if self.status not in [self.Status.PROCESSING, self.Status.APPROVED]:
            raise ValueError("Only processing or approved releases can be failed")
            
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.save()

    @property
    def requires_approval(self):
        """Check if release requires approval"""
        return self.status == self.Status.PENDING and self.approval_requested_at is not None

    @property
    def is_final(self):
        """Check if release is in a final state"""
        return self.status in [self.Status.COMPLETED, self.Status.FAILED, self.Status.REJECTED] 
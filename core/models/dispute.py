from django.db import models
from django.utils import timezone
from django.conf import settings

class Dispute(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        IN_REVIEW = 'IN_REVIEW', 'Under Review'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'
        ESCALATED = 'ESCALATED', 'Escalated'

    class Type(models.TextChoices):
        PAYMENT = 'PAYMENT', 'Payment Issue'
        MILESTONE = 'MILESTONE', 'Milestone Dispute'
        QUALITY = 'QUALITY', 'Quality Issue'
        OTHER = 'OTHER', 'Other'

    # Core Fields
    transaction = models.ForeignKey('Transaction', on_delete=models.PROTECT, related_name='disputes')
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='disputes_raised')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes_assigned')
    
    # Details
    dispute_type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    title = models.CharField(max_length=200)
    description = models.TextField()
    amount_in_dispute = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolution = models.TextField(blank=True)
    resolution_type = models.CharField(max_length=50, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes_resolved')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['dispute_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Dispute #{self.id} - {self.title}"

    def assign_to(self, user):
        """Assign dispute to a moderator/admin."""
        self.assigned_to = user
        self.status = self.Status.IN_REVIEW
        self.save()

    def resolve(self, resolution_text, resolution_type, resolved_by):
        """Resolve the dispute with given resolution."""
        self.resolution = resolution_text
        self.resolution_type = resolution_type
        self.resolved_by = resolved_by
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save()

    def escalate(self):
        """Escalate the dispute to higher authority."""
        self.status = self.Status.ESCALATED
        self.save()

    def close(self):
        """Close the dispute."""
        self.status = self.Status.CLOSED
        self.save()

class DisputeEvidence(models.Model):
    """Model to store evidence for disputes."""
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidence')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='dispute_evidence/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidence for Dispute #{self.dispute.id} - {self.title}"

class DisputeComment(models.Model):
    """Model to store comments on disputes."""
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_internal = models.BooleanField(default=False)  # For admin/staff comments

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on Dispute #{self.dispute.id} by {self.author}" 
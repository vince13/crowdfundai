from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

class Report(models.Model):
    class ReportStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Report Approved'
        REJECTED = 'REJECTED', 'Report Rejected'
        RESOLVED = 'RESOLVED', 'Issue Resolved'

    class ReportReason(models.TextChoices):
        INAPPROPRIATE = 'INAPPROPRIATE', 'Inappropriate Content'
        SPAM = 'SPAM', 'Spam'
        MISLEADING = 'MISLEADING', 'Misleading Information'
        FRAUD = 'FRAUD', 'Fraudulent Activity'
        OTHER = 'OTHER', 'Other'

    # Content that is being reported (Generic Foreign Key)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Report details
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                               null=True, related_name='reports_submitted')
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=ReportStatus.choices, 
                            default=ReportStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Moderation details
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                null=True, related_name='reports_moderated')
    moderation_notes = models.TextField(blank=True)
    moderated_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at']

class ContentModeration(models.Model):
    class ModerationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        FLAGGED = 'FLAGGED', 'Flagged for Review'

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    status = models.CharField(max_length=20, choices=ModerationStatus.choices, 
                            default=ModerationStatus.PENDING)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                null=True, related_name='moderated_content')
    moderation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['content_type', 'object_id']

class ModerationLog(models.Model):
    class ActionType(models.TextChoices):
        REVIEW = 'REVIEW', 'Content Review'
        APPROVE = 'APPROVE', 'Content Approval'
        REJECT = 'REJECT', 'Content Rejection'
        FLAG = 'FLAG', 'Content Flagging'
        UPDATE = 'UPDATE', 'Status Update'

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ActionType.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] 
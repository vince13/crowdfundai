from django.db import models
from django.utils import timezone

class ProjectRequest(models.Model):
    """Model for storing project requests from the hire us form"""
    
    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        CONTACTED = 'CONTACTED', 'Contacted'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'
    
    class ProjectType(models.TextChoices):
        WEB = 'web', 'Web Solution'
        MOBILE = 'mobile', 'Mobile App'
        AI = 'ai', 'AI/ML Solution'
        BLOCKCHAIN = 'blockchain', 'Blockchain'
        DATACENTER = 'datacenter', 'Data Center'
        AUTONOMOUS = 'autonomous', 'Autonomous'
        DEFENCE = 'defence', 'Defence'
        OTHER = 'other', 'Other'
    
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.project_type} ({self.status})" 
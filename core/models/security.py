from django.db import models
from django.conf import settings

class SecurityAuditLog(models.Model):
    """Model for tracking security-related events"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='security_logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('failure', 'Failure'),
            ('warning', 'Warning')
        ]
    )
    ip_address = models.GenericIPAddressField(null=True)
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', 'status']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Security Audit Log'
        verbose_name_plural = 'Security Audit Logs'
    
    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}" 
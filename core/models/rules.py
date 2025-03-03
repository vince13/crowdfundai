from django.db import models
from django.core.exceptions import ValidationError
import json

class BusinessRule(models.Model):
    """Model for storing configurable business rules"""
    
    RULE_TYPES = [
        ('investment', 'Investment Rules'),
        ('app_submission', 'App Submission Rules'),
        ('user', 'User Rules'),
        ('moderation', 'Moderation Rules')
    ]
    
    name = models.CharField(max_length=100, unique=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['rule_type', 'name']
        indexes = [
            models.Index(fields=['rule_type', 'is_active']),
            models.Index(fields=['name', 'is_active']),
        ]
        unique_together = ['rule_type', 'name']
    
    def __str__(self):
        return f"{self.rule_type} - {self.name}"
    
    def clean(self):
        """Validate the rule value is valid JSON"""
        try:
            if isinstance(self.value, str):
                json.loads(self.value)
        except json.JSONDecodeError:
            raise ValidationError({'value': 'Invalid JSON format'})
    
    @classmethod
    def get_rules_by_type(cls, rule_type):
        """Get all active rules for a specific type"""
        return list(cls.objects.filter(
            rule_type=rule_type,
            is_active=True
        ).values('name', 'value')) 
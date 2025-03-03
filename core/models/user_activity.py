from django.db import models
from django.conf import settings

class UserActivity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity',
        unique=True
    )
    last_activity = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'User Activities'
        app_label = 'core'

    def __str__(self):
        return f"{self.user.username}'s activity"

    @classmethod
    def update_activity(cls, user, ip_address):
        """Update or create user activity"""
        cls.objects.update_or_create(
            user=user,
            defaults={'ip_address': ip_address}
        ) 
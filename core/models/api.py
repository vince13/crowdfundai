from django.db import models
from django.conf import settings

class APIRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    response_time = models.FloatField()  # in milliseconds
    status_code = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'API Request'
        verbose_name_plural = 'API Requests'

    def __str__(self):
        return f"{self.method} {self.endpoint} ({self.status_code})"

class APIError(models.Model):
    request = models.ForeignKey(APIRequest, on_delete=models.CASCADE)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    stack_trace = models.TextField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'API Error'
        verbose_name_plural = 'API Errors'

    def __str__(self):
        return f"{self.error_type} at {self.timestamp}" 
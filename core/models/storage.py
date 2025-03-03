from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class StorageQuota(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_size = models.BigIntegerField(default=0)  # Total size in bytes
    max_size = models.BigIntegerField(default=50 * 1024 * 1024)  # 50MB default per user
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.total_size}/{self.max_size} bytes used"

    def can_upload(self, file_size):
        return self.total_size + file_size <= self.max_size

    def add_file(self, file_size):
        if not self.can_upload(file_size):
            raise ValidationError("Storage quota exceeded")
        self.total_size += file_size
        self.save()

    def remove_file(self, file_size):
        self.total_size = max(0, self.total_size - file_size)
        self.save()

    @property
    def usage_percentage(self):
        return (self.total_size / self.max_size) * 100 if self.max_size > 0 else 0 
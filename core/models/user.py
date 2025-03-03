# This is the old user model that was moved to the base.py file 
# DO NOT ACTIVATE THIS FILE 

# from django.contrib.auth.models import AbstractUser
# from django.db import models
# from django.utils import timezone
# from django.utils.translation import gettext_lazy as _
# from django.core.validators import MinValueValidator, MaxValueValidator

# class User(AbstractUser):
#     class Role(models.TextChoices):
#         ADMIN = 'ADMIN', 'Admin'
#         DEVELOPER = 'DEVELOPER', 'Developer'
#         INVESTOR = 'INVESTOR', 'Investor'
    
#     email = models.EmailField(unique=True)
#     role = models.CharField(
#         max_length=10,
#         choices=Role.choices,
#         default=Role.INVESTOR
#     )
#     bio = models.TextField(blank=True)
#     profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
#     is_email_verified = models.BooleanField(default=False)
    
#     # 2FA fields
#     two_factor_enabled = models.BooleanField(default=False)
#     two_factor_secret = models.CharField(max_length=32, null=True, blank=True)
    
#     # Account deletion fields
#     is_deleted = models.BooleanField(default=False)
#     deleted_at = models.DateTimeField(null=True, blank=True)
#     deletion_reason = models.TextField(null=True, blank=True)
    
#     # Session management
#     last_login_ip = models.GenericIPAddressField(null=True, blank=True)
#     last_login_user_agent = models.CharField(max_length=255, null=True, blank=True)
#     failed_login_attempts = models.IntegerField(default=0)
#     last_failed_login = models.DateTimeField(null=True, blank=True)
#     account_locked_until = models.DateTimeField(null=True, blank=True)

#     def is_developer(self):
#         return self.role == self.Role.DEVELOPER

#     def is_investor(self):
#         return self.role == self.Role.INVESTOR

#     def get_total_investments(self):
#         from .investment import Investment
#         return Investment.objects.filter(investor=self).count()
    
#     def soft_delete(self, reason=None):
#         """Soft delete the user account"""
#         self.is_deleted = True
#         self.deleted_at = timezone.now()
#         self.deletion_reason = reason
#         self.email = f"deleted_{self.id}_{self.email}"  # Preserve email uniqueness
#         self.username = f"deleted_{self.id}_{self.username}"  # Preserve username uniqueness
#         self.is_active = False
#         self.save()
    
#     def record_login_attempt(self, success, ip_address=None, user_agent=None):
#         """Record login attempt and handle account locking"""
#         if success:
#             self.failed_login_attempts = 0
#             self.last_login_ip = ip_address
#             self.last_login_user_agent = user_agent
#         else:
#             self.failed_login_attempts += 1
#             self.last_failed_login = timezone.now()
            
#             # Lock account after 5 failed attempts
#             if self.failed_login_attempts >= 5:
#                 self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
#         self.save()
    
#     def is_account_locked(self):
#         """Check if account is temporarily locked"""
#         if self.account_locked_until and self.account_locked_until > timezone.now():
#             return True
#         return False

#     class Meta:
#         db_table = 'users'
#         verbose_name = 'User'
#         verbose_name_plural = 'Users' 
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.apps import apps
from django.core.exceptions import ValidationError

def get_storage_quota_model():
    return apps.get_model('core', 'StorageQuota')

@receiver(post_save, sender='core.User')
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences when a new user is created"""
    if created:
        NotificationPreference = apps.get_model('core', 'NotificationPreference')
        NotificationPreference.objects.create(
            user=instance,
            email_notifications=True,
            push_notifications=True,
            investment_notifications=True,
            price_alerts=True,
            system_notifications=True,
            milestone_notifications=True,
            app_update_notifications=True,
            funding_goal_notifications=True,
            dividend_notifications=True,
            security_notifications=True,
            maintenance_notifications=True,
            news_notifications=True,
            app_approval_notifications=True
        )

@receiver(post_save, sender='core.User')
def save_notification_preferences(sender, instance, **kwargs):
    """Save notification preferences when user is updated"""
    try:
        instance.notification_preferences.save()
    except AttributeError:
        NotificationPreference = apps.get_model('core', 'NotificationPreference')
        NotificationPreference.objects.create(user=instance)

@receiver(post_delete, sender='core.Investment')
def update_share_ownership_on_investment_delete(sender, instance, **kwargs):
    """Update ShareOwnership when an Investment is deleted"""
    try:
        ShareOwnership = apps.get_model('core', 'ShareOwnership')
        # Get the ShareOwnership record
        ownership = ShareOwnership.objects.get(
            user=instance.investor,
            app=instance.app
        )
        
        # Subtract the percentage that was bought in this investment
        ownership.percentage_owned -= instance.percentage_bought
        
        # If no shares left, delete the ownership record
        if ownership.percentage_owned <= 0:
            ownership.delete()
        else:
            ownership.save()
            
        # Update app's remaining percentage
        instance.app.remaining_percentage += instance.percentage_bought
        instance.app.save()
        
    except ShareOwnership.DoesNotExist:
        pass  # No ownership record found, nothing to update

@receiver(pre_save)
def check_file_upload(sender, instance, **kwargs):
    """Check if the file can be uploaded within the user's quota"""
    if hasattr(instance, 'file') and hasattr(instance, 'user'):
        StorageQuota = get_storage_quota_model()
        if not hasattr(instance.user, 'storagequota'):
            StorageQuota.objects.create(user=instance.user)
        
        # If this is an update, get the old file size
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            old_size = old_instance.file.size
        except sender.DoesNotExist:
            old_size = 0
        
        # Check if the new file can be accommodated
        new_size = instance.file.size
        size_diff = new_size - old_size
        
        if size_diff > 0:  # Only check if the new file is larger
            if not instance.user.storagequota.can_upload(size_diff):
                raise ValidationError("Storage quota exceeded")
            
            instance.user.storagequota.add_file(size_diff)

@receiver(post_delete)
def remove_file_from_quota(sender, instance, **kwargs):
    """Update storage quota when a file is deleted"""
    if hasattr(instance, 'file') and hasattr(instance, 'user'):
        if hasattr(instance.user, 'storagequota'):
            instance.user.storagequota.remove_file(instance.file.size)

@receiver(post_save, sender='core.User')
def set_superuser_role(sender, instance, created, **kwargs):
    """Set role to ADMIN for superusers"""
    if instance.is_superuser and instance.role != sender.Role.ADMIN:
        instance.role = sender.Role.ADMIN
        # Use update to avoid recursive signal calls
        sender.objects.filter(pk=instance.pk).update(role=sender.Role.ADMIN)
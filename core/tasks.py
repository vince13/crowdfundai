from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Notification
from django.core.management import call_command
import logging
from django.conf import settings
import os
from core.services.notifications import NotificationService
from core.services.backup import BackupService

logger = logging.getLogger(__name__)

@shared_task
def cleanup_old_notifications():
    # Delete notifications older than 30 days
    threshold = timezone.now() - timedelta(days=30)
    Notification.objects.filter(created_at__lt=threshold).delete()

@shared_task
def cleanup_read_notifications():
    # Delete read notifications older than 7 days
    threshold = timezone.now() - timedelta(days=7)
    Notification.objects.filter(
        is_read=True,
        created_at__lt=threshold
    ).delete() 

@shared_task
def send_scheduled_notification(user_id, type, title, message, link=''):
    """Celery task for sending scheduled notifications"""
    from .models import User
    from .services.notifications import NotificationService
    
    try:
        user = User.objects.get(id=user_id)
        NotificationService.create_notification(
            user=user,
            type=type,
            title=title,
            message=message,
            link=link
        )
    except User.DoesNotExist:
        pass

@shared_task
def check_platform_fees():
    """Run the platform fee check command"""
    try:
        logger.info('Starting platform fee check task')
        call_command('check_platform_fees')
        logger.info('Completed platform fee check task')
    except Exception as e:
        logger.error(f'Error in platform fee check task: {str(e)}')
        raise 

@shared_task
def verify_backup_completion():
    """Verify that daily backups were completed successfully."""
    try:
        backup_service = BackupService()
        backups = backup_service.list_backups()
        today = datetime.now().strftime('%Y%m%d')
        
        # Check for today's backups
        db_backup = any(today in b['filename'] for b in backups['database'])
        media_backup = any(today in b['filename'] for b in backups['media'])
        config_backup = any(today in b['filename'] for b in backups['config'])
        
        missing = []
        if not db_backup:
            missing.append('DB')
        if not media_backup:
            missing.append('Media')
        if not config_backup:
            missing.append('Config')
            
        if missing:
            NotificationService.notify_admin_backup_failure(
                "Daily backup incomplete",
                f"Missing backups: {' '.join(missing)}"
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Backup verification failed: {str(e)}")
        NotificationService.notify_admin_backup_failure(
            "Backup verification failed",
            f"Error: {str(e)}"
        )
        return False

@shared_task
def check_backup_integrity():
    """Check integrity of recent backups."""
    try:
        backup_service = BackupService()
        backups = backup_service.list_backups()
        check_date = datetime.now() - timedelta(days=1)  # Check yesterday's backup
        date_str = check_date.strftime('%Y%m%d')
        
        issues = []
        
        # Check each type of backup
        for backup_type in ['database', 'media', 'config']:
            # Find yesterday's backup
            yesterday_backup = next(
                (b for b in backups[backup_type] if date_str in b['filename']),
                None
            )
            
            if not yesterday_backup:
                issues.append(f"No {backup_type} backup found for {date_str}")
                continue
                
            # Verify backup integrity
            result = backup_service.verify_backup(
                yesterday_backup['path'],
                backup_type.rstrip('s')  # Remove 's' from type for service method
            )
            
            if not result['success']:
                issues.append(f"{backup_type.title()} backup verification failed: {result['message']}")
        
        if issues:
            NotificationService.notify_admin_backup_failure(
                "Backup integrity check failed",
                "Issues found: " + ", ".join(issues)
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Backup integrity check failed: {str(e)}")
        NotificationService.notify_admin_backup_failure(
            "Backup integrity check failed",
            f"Error: {str(e)}"
        )
        return False

@shared_task
def retry_webhook_delivery(transaction_id):
    """Retry webhook delivery for failed attempts"""
    from .models import Transaction
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        if transaction.webhook_status not in ['FAILED', 'RETRYING']:
            return False
            
        # Attempt to deliver webhook
        success = deliver_webhook(transaction)  # Implement this in your webhook service
        transaction.log_webhook_attempt(success)
        
        return success
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found for webhook retry")
        return False
    except Exception as e:
        logger.error(f"Error retrying webhook for transaction {transaction_id}: {str(e)}")
        return False

@shared_task
def monitor_pending_webhooks():
    """Check for pending webhooks and retry failed ones"""
    from .models import Transaction
    
    # Find transactions with pending or failed webhooks
    pending_transactions = Transaction.objects.filter(
        webhook_status__in=['PENDING', 'RETRYING'],
        webhook_attempts__lt=3,  # Less than max attempts
        created_at__gte=timezone.now() - timedelta(days=7)  # Within last 7 days
    )
    
    for transaction in pending_transactions:
        retry_webhook_delivery.delay(transaction.id)

@shared_task
def alert_failed_transactions():
    """Send alerts for failed transactions and webhooks"""
    from .models import Transaction
    from .services.notifications import NotificationService
    
    # Check for failed transactions in the last hour
    hour_ago = timezone.now() - timedelta(hours=1)
    failed_transactions = Transaction.objects.filter(
        status='FAILED',
        created_at__gte=hour_ago
    )
    
    # Check for failed webhooks
    failed_webhooks = Transaction.objects.filter(
        webhook_status='FAILED',
        last_webhook_attempt__gte=hour_ago
    )
    
    if failed_transactions.exists() or failed_webhooks.exists():
        # Send notification to admin
        NotificationService.notify_admin_payment_issues(
            failed_transactions=failed_transactions,
            failed_webhooks=failed_webhooks
        )

@shared_task
def cleanup_transaction_logs():
    """Clean up old transaction logs while preserving important data"""
    from .models import Transaction
    
    # Keep only last 30 days of detailed logs
    threshold_date = timezone.now() - timedelta(days=30)
    old_transactions = Transaction.objects.filter(created_at__lt=threshold_date)
    
    for transaction in old_transactions:
        # Preserve important data but clear detailed logs
        transaction.webhook_logs = []
        transaction.debug_info = {}
        transaction.save() 
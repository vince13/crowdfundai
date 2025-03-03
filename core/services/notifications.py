from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
from ..models import Notification
from firebase_admin import messaging
from django.utils import timezone
from django.urls import reverse
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_notification(user, type, title, message, link=''):
        """Create a notification for a user"""
        return Notification.objects.create(
            user=user,
            type=type,
            title=title,
            message=message,
            link=link
        )

    @staticmethod
    def send_push_notification(user, title, message, data=None):
        """
        Send a push notification to a user if they have opted in for push notifications.
        """
        if not user.notification_preferences.push_notifications:
            return
        
        if not hasattr(user, 'device_tokens'):
            return
            
        msg = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message
            ),
            data=data or {},
            token=user.device_tokens.token
        )
        
        return messaging.send(msg)

    @staticmethod
    def send_email_notification(user, subject, template, context):
        """
        Send an email notification to a user if they have opted in for email notifications.
        """
        if not user.notification_preferences.email_notifications:
            return
            
        html_content = render_to_string(template, context)
        
        send_mail(
            subject=subject,
            message='',  # Empty string as we're using HTML content
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content
        )
    
    @staticmethod
    def send_notification_digest(frequency='DAILY'):
        """
        Send notification digest emails to users based on their preferences.
        """
        if frequency == 'DAILY':
            cutoff = timezone.now() - timezone.timedelta(days=1)
        elif frequency == 'WEEKLY':
            cutoff = timezone.now() - timezone.timedelta(days=7)
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
            
        users = User.objects.filter(
            notification_preferences__notification_frequency=frequency
        )
        
        for user in users:
            notifications = Notification.objects.filter(
                user=user,
                created_at__gte=cutoff
            )
            
            if notifications.exists():
                NotificationService.send_email_notification(
                    user=user,
                    subject=f'Your {frequency.title()} Notification Digest',
                    template='core/emails/notification_digest.html',
                    context={'notifications': notifications}
                )
    
    @staticmethod
    def notify_app_submission(app):
        """
        Notify admins about a new app submission.
        """
        # Get all admin users
        admin_users = User.objects.filter(role=User.Role.ADMIN)
        
        for admin in admin_users:
            # Create in-app notification
            Notification.objects.create(
                user=admin,
                type=Notification.Type.APP_APPROVAL,
                title='New App Submission',
                message=f'New app "{app.name}" submitted by {app.developer.email} requires review.',
                link=f'/admin/core/applisting/{app.id}/change/'
            )
            
            # Send email notification
            NotificationService.send_email_notification(
                user=admin,
                subject='New App Submission Requires Review',
                template='core/emails/app_submission.html',
                context={
                    'app': app,
                    'admin': admin,
                    'site_url': settings.SITE_URL
                }
            )
    
    @staticmethod
    def notify_app_approval(app):
        """
        Notify the developer about app approval.
        """
        # Create in-app notification
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_APPROVAL,
            title='App Approved',
            message=f'Your app "{app.name}" has been approved and is now listed.',
            link=f'/apps/{app.id}/'
        )
        
        # Send email notification
        NotificationService.send_email_notification(
            user=app.developer,
            subject='Your App Has Been Approved',
            template='core/emails/app_approval.html',
            context={
                'app': app,
                'site_url': settings.SITE_URL
            }
        )
        
        # Add push notification
        NotificationService.send_push_notification(
            user=app.developer,
            title='App Approved',
            message=f'Your app "{app.name}" has been approved and is now listed.'
        )
    
    @staticmethod
    def notify_app_rejection(app, feedback):
        """
        Notify the developer about app rejection.
        """
        # Create in-app notification
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_APPROVAL,
            title='App Needs Changes',
            message=f'Your app "{app.name}" requires changes before it can be approved.',
            link=f'/apps/{app.id}/'
        )
        
        # Send email notification
        NotificationService.send_email_notification(
            user=app.developer,
            subject='Your App Requires Changes',
            template='core/emails/app_rejection.html',
            context={
                'app': app,
                'feedback': feedback,
                'site_url': settings.SITE_URL
            }
        )
        
        # Add push notification
        NotificationService.send_push_notification(
            user=app.developer,
            title='App Needs Changes',
            message=f'Your app "{app.name}" requires changes before it can be approved.'
        )

    @classmethod
    def notify_community_suggestion(cls, app):
        """Notify admins about a new community app suggestion."""
        admins = User.objects.filter(role=User.Role.ADMIN)
        
        for admin in admins:
            Notification.objects.create(
                user=admin,
                type=Notification.Type.APP_APPROVAL,
                title="New Community App Suggestion",
                message=f"A new app '{app.name}' has been suggested by the community. Please review.",
                link=reverse('core:admin_review_app', args=[app.pk])
            )

    @classmethod
    def notify_suggestion_trending(cls, app):
        """Notify admins and the suggester when an app becomes trending."""
        # Notify admins
        admins = User.objects.filter(role=User.Role.ADMIN)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                type=Notification.Type.APP_UPDATE,
                title="Community App Trending",
                message=f"The suggested app '{app.name}' is now trending with high community interest.",
                link=reverse('core:app_detail', args=[app.pk])
            )
        
        # Notify the suggester
        if app.suggested_by:
            Notification.objects.create(
                user=app.suggested_by,
                type=Notification.Type.APP_UPDATE,
                title="Your Suggested App is Trending!",
                message=f"Congratulations! Your suggested app '{app.name}' is now trending.",
                link=reverse('core:app_detail', args=[app.pk])
            )

    @classmethod
    def notify_suggestion_status_change(cls, app, old_status, new_status):
        """Notify the suggester about status changes."""
        if not app.suggested_by:
            return
        
        status_messages = {
            AppListing.Status.ACTIVE: "has been approved and is now visible to the community",
            AppListing.Status.REJECTED: "has been reviewed but not selected for development at this time",
            AppListing.Status.IN_DEVELOPMENT: "has been selected for development",
        }
        
        if new_status in status_messages:
            Notification.objects.create(
                user=app.suggested_by,
                type=Notification.Type.APP_APPROVAL,
                title=f"Suggestion Status Update: {app.name}",
                message=f"Your suggested app '{app.name}' {status_messages[new_status]}.",
                link=reverse('core:app_detail', args=[app.pk])
            )

    @classmethod
    def notify_private_comment(cls, app, comment):
        """Notify the app developer about a new private comment."""
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_UPDATE,
            title="New Private Comment",
            message=f"A new private comment has been added to your app '{app.name}'.",
            link=f'/apps/{app.pk}/'
        )

    @classmethod
    def notify_community_comment(cls, app, comment):
        """Notify relevant users about a new community comment."""
        # Notify the app developer
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_UPDATE,
            title="New Community Comment",
            message=f"A new community comment has been added to your app '{app.name}'.",
            link=f'/apps/{app.pk}/'
        )

        # If this is a reply, notify the parent comment author
        if comment.parent and comment.parent.user != app.developer:
            Notification.objects.create(
                user=comment.parent.user,
                type=Notification.Type.APP_UPDATE,
                title="New Reply to Your Comment",
                message=f"Someone replied to your comment on '{app.name}'.",
                link=f'/apps/{app.pk}/'
            )

    @classmethod
    def notify_developer_funding_complete(cls, app, amount, platform_fee):
        """Notify developer when funding is complete and fees are processed"""
        notification = Notification.objects.create(
            user=app.developer,
            type=Notification.Type.FUNDING_COMPLETE,
            title=f"Funding Complete - {app.name}",
            message=(
                f"Congratulations! Your app {app.name} has completed its funding round.\n"
                f"Total Amount: ₦{amount:,.2f}\n"
                f"Platform Fee (5%): ₦{platform_fee:,.2f}\n"
                f"Net Amount: ₦{amount - platform_fee:,.2f}\n\n"
                f"The funds have been released to your account."
            ),
            link=reverse('core:app_detail', kwargs={'pk': app.id})
        )
        
        # Send email notification
        cls.send_email_notification(
            user=app.developer,
            subject=f"Funding Complete - {app.name}",
            template='core/emails/funding_complete.html',
            context={
                'app_name': app.name,
                'total_amount': amount,
                'platform_fee': platform_fee,
                'net_amount': amount - platform_fee,
                'app_url': reverse('core:app_detail', kwargs={'pk': app.id}),
                'site_url': settings.SITE_URL
            }
        )
        
        return notification

    @classmethod
    def notify_admins_fee_processing_failed(cls, app, error):
        """Notify admins when platform fee processing fails"""
        try:
            # Get all admin users
            admins = User.objects.filter(is_staff=True)
            
            for admin in admins:
                # Create notification
                Notification.objects.create(
                    user=admin,
                    type=Notification.Type.SYSTEM_ERROR,
                    title=f"Platform Fee Processing Failed - {app.name}",
                    message=(
                        f"Platform fee processing failed for app {app.name} (ID: {app.id}).\n"
                        f"Error: {error}\n\n"
                        f"Please check the platform fee dashboard and process the fee manually if needed."
                    ),
                    link=f"/admin/platform-fees/",
                    severity=Notification.Severity.HIGH
                )
                
                # Send email notification
                cls.send_email_notification(
                    user=admin,
                    subject=f"Platform Fee Processing Failed - {app.name}",
                    template="core/emails/platform_fee_failed.html",
                    context={
                        'app': app,
                        'error': error,
                        'admin': admin,
                        'site_url': settings.SITE_URL
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to send admin notification for fee processing failure: {str(e)}")
            # Don't raise the error to prevent cascading failures

    @classmethod
    def notify_seller_contact(cls, app, sender, message):
        """
        Notify the app seller about a new contact request.
        
        Args:
            app: The AppListing instance
            sender: The User instance who sent the message
            message: The message content
        """
        # Create in-app notification
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_UPDATE,
            title='New Buyer Interest',
            message=f'{sender.username} is interested in buying your app "{app.name}".',
            link=reverse('core:app_detail', args=[app.pk])
        )
        
        # Send email notification
        cls.send_email_notification(
            user=app.developer,
            subject=f'New Interest in {app.name}',
            template='core/emails/seller_contact.html',
            context={
                'app': app,
                'sender': sender,
                'message': message,
                'site_url': settings.SITE_URL
            }
        )
        
        # Add push notification
        cls.send_push_notification(
            user=app.developer,
            title='New Buyer Interest',
            message=f'{sender.username} is interested in buying your app "{app.name}".'
        )
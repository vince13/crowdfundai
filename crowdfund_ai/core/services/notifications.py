from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from ..models import Notification

User = get_user_model()

class NotificationService:
    @staticmethod
    def send_email_notification(user, subject, template, context):
        """Send an email notification to a user"""
        if not user.notification_preferences.email_notifications:
            return
            
        html_content = render_to_string(template, context)
        
        send_mail(
            subject=subject,
            message='',  # Empty string for plain text (using HTML)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content
        )

    @staticmethod
    def notify_app_submission(app):
        """Notify admins about a new app submission"""
        # Get all admin users
        admins = User.objects.filter(role=User.Role.ADMIN)
        
        for admin in admins:
            # Create in-app notification
            Notification.objects.create(
                user=admin,
                type=Notification.Type.APP_APPROVAL,
                title='New App Submission',
                message=f'A new app "{app.name}" has been submitted by {app.developer.username} for review.',
                link=f'/admin/apps/{app.id}/review/'
            )
            
            # Send email notification
            NotificationService.send_email_notification(
                user=admin,
                subject='New App Submission',
                template='core/emails/app_submission.html',
                context={
                    'app': app,
                    'admin': admin
                }
            )

    @staticmethod
    def notify_app_approval(app):
        """Notify developer about app approval"""
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_APPROVAL,
            title='App Approved',
            message=f'Your app "{app.name}" has been approved and is now live.',
            link=f'/apps/{app.id}/'
        )
        
        NotificationService.send_email_notification(
            user=app.developer,
            subject='App Approved',
            template='core/emails/app_approval.html',
            context={
                'app': app,
                'user': app.developer
            }
        )

    @staticmethod
    def notify_app_rejection(app, feedback):
        """Notify developer about app rejection"""
        Notification.objects.create(
            user=app.developer,
            type=Notification.Type.APP_APPROVAL,
            title='App Rejected',
            message=f'Your app "{app.name}" was not approved. Feedback: {feedback}',
            link=f'/apps/{app.id}/'
        )
        
        NotificationService.send_email_notification(
            user=app.developer,
            subject='App Submission Update',
            template='core/emails/app_rejection.html',
            context={
                'app': app,
                'user': app.developer,
                'feedback': feedback
            }
        ) 
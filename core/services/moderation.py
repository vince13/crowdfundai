from django.utils import timezone
from ..models import Report, ContentModeration, ModerationLog
from ..services.notifications import NotificationService

class ModerationService:
    @staticmethod
    def report_content(content_object, reporter, reason, description):
        """Create a new content report"""
        content_type = ContentType.objects.get_for_model(content_object)
        
        report = Report.objects.create(
            content_type=content_type,
            object_id=content_object.id,
            reporter=reporter,
            reason=reason,
            description=description
        )

        # Create or update content moderation entry
        moderation, created = ContentModeration.objects.get_or_create(
            content_type=content_type,
            object_id=content_object.id,
            defaults={'status': ContentModeration.ModerationStatus.FLAGGED}
        )

        # Notify admins about new report
        NotificationService.notify_admins(
            title="New Content Report",
            message=f"New content report submitted for {content_object}",
            link=f"/administration/moderation/reports/{report.id}/"
        )

        return report

    @staticmethod
    def review_content(content_object, moderator, status, notes=""):
        """Review and update content moderation status"""
        content_type = ContentType.objects.get_for_model(content_object)
        
        moderation, created = ContentModeration.objects.get_or_create(
            content_type=content_type,
            object_id=content_object.id,
            defaults={'status': status}
        )

        if not created:
            moderation.status = status
            
        moderation.moderator = moderator
        moderation.moderation_notes = notes
        moderation.save()

        # Log the moderation action
        ModerationLog.objects.create(
            content_type=content_type,
            object_id=content_object.id,
            moderator=moderator,
            action=ModerationLog.ActionType.REVIEW,
            notes=notes
        )

        # Update related reports
        Report.objects.filter(
            content_type=content_type,
            object_id=content_object.id,
            status=Report.ReportStatus.PENDING
        ).update(
            status=Report.ReportStatus.RESOLVED,
            moderator=moderator,
            moderation_notes=notes,
            moderated_at=timezone.now()
        )

        # Notify content owner
        if hasattr(content_object, 'user'):
            NotificationService.notify_user(
                content_object.user,
                title="Content Moderation Update",
                message=f"Your content has been reviewed and marked as {status}",
                notification_type="MODERATION"
            )

        return moderation

    @staticmethod
    def get_pending_reports():
        """Get all pending reports"""
        return Report.objects.filter(status=Report.ReportStatus.PENDING)

    @staticmethod
    def get_content_status(content_object):
        """Get moderation status for content"""
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            moderation = ContentModeration.objects.get(
                content_type=content_type,
                object_id=content_object.id
            )
            return moderation.status
        except ContentModeration.DoesNotExist:
            return ContentModeration.ModerationStatus.PENDING 
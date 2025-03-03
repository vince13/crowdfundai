from django.core.management.base import BaseCommand
from django.db import transaction

from core.models.base import (
    User, AppListing, Investment, ShareOwnership, Transaction,
    Notification, PlatformFeeTransaction, Blog, BlogCategory,
    Advertisement
)
from core.models.project import ProjectMilestone, ProjectUpdate, ProjectTag
from core.models.project_request import ProjectRequest
from core.models.dispute import Dispute, DisputeEvidence
from core.models.subscription import SubscriptionPlan, Subscription
from core.models.release import Release
from core.models.escrow import EscrowRelease
from core.models.investment_receipt import InvestmentCertificate

class Command(BaseCommand):
    help = 'Deletes ALL data from the database'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Store counts before deletion
                counts = {
                    'Users': User.objects.count(),
                    'Apps': AppListing.objects.count(),
                    'Investments': Investment.objects.count(),
                    'Share Ownerships': ShareOwnership.objects.count(),
                    'Transactions': Transaction.objects.count(),
                    'Notifications': Notification.objects.count(),
                    'Platform Fee Transactions': PlatformFeeTransaction.objects.count(),
                    'Project Milestones': ProjectMilestone.objects.count(),
                    'Project Updates': ProjectUpdate.objects.count(),
                    'Project Tags': ProjectTag.objects.count(),
                    'Project Requests': ProjectRequest.objects.count(),
                    'Blog Posts': Blog.objects.count(),
                    'Blog Categories': BlogCategory.objects.count(),
                    'Advertisements': Advertisement.objects.count(),
                    'Subscription Plans': SubscriptionPlan.objects.count(),
                    'Subscriptions': Subscription.objects.count(),
                    'Disputes': Dispute.objects.count(),
                    'Dispute Evidence': DisputeEvidence.objects.count(),
                    'Releases': Release.objects.count(),
                    'Escrow Releases': EscrowRelease.objects.count(),
                    'Investment Certificates': InvestmentCertificate.objects.count(),
                }

                # Delete all data
                EscrowRelease.objects.all().delete()
                Release.objects.all().delete()
                DisputeEvidence.objects.all().delete()
                Dispute.objects.all().delete()
                Subscription.objects.all().delete()
                SubscriptionPlan.objects.all().delete()
                Advertisement.objects.all().delete()
                Blog.objects.all().delete()
                BlogCategory.objects.all().delete()
                ProjectRequest.objects.all().delete()
                ProjectTag.objects.all().delete()
                ProjectUpdate.objects.all().delete()
                ProjectMilestone.objects.all().delete()
                PlatformFeeTransaction.objects.all().delete()
                Notification.objects.all().delete()
                Transaction.objects.all().delete()
                ShareOwnership.objects.all().delete()
                Investment.objects.all().delete()
                InvestmentCertificate.objects.all().delete()
                AppListing.objects.all().delete()
                User.objects.all().delete()

                # Print summary
                self.stdout.write(self.style.SUCCESS('Successfully deleted all data:'))
                for model, count in counts.items():
                    self.stdout.write(f'  - {model}: {count}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise 

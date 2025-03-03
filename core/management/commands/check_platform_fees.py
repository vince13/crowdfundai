from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import AppListing, PlatformFeeTransaction
from core.services.payments import PaymentService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check for fully funded apps without platform fees and process them'

    def handle(self, *args, **options):
        try:
            # Get all fully funded apps
            funded_apps = AppListing.objects.filter(
                status=AppListing.Status.FUNDED
            ).exclude(
                id__in=PlatformFeeTransaction.objects.values_list('app_id', flat=True)
            )
            
            if not funded_apps.exists():
                self.stdout.write(self.style.SUCCESS('No funded apps missing platform fees found.'))
                return
                
            self.stdout.write(f'Found {funded_apps.count()} funded apps without platform fees.')
            
            for app in funded_apps:
                try:
                    self.stdout.write(f'Processing platform fee for app {app.id} ({app.name})...')
                    PaymentService.handle_funding_completion(app)
                    self.stdout.write(self.style.SUCCESS(f'Successfully processed platform fee for app {app.id}'))
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing platform fee for app {app.id}: {str(e)}')
                    )
                    logger.error(f'Error processing platform fee for app {app.id}: {str(e)}')
                    continue
                    
            self.stdout.write(self.style.SUCCESS('Completed platform fee check.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing platform fee check: {str(e)}'))
            logger.error(f'Error processing platform fee check: {str(e)}') 
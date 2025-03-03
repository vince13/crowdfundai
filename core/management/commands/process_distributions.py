from django.core.management.base import BaseCommand
from core.services.revenue.distribution import RevenueDistributionService
from django.utils import timezone

class Command(BaseCommand):
    help = 'Process pending revenue distributions'

    def handle(self, *args, **options):
        service = RevenueDistributionService()
        self.stdout.write(f'Starting distribution processing at {timezone.now()}')
        
        try:
            service.schedule_distributions()
            self.stdout.write(self.style.SUCCESS('Successfully processed distributions'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing distributions: {str(e)}')
            ) 
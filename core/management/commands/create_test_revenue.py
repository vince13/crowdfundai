from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import AppListing, Revenue
from decimal import Decimal
import random
from datetime import timedelta

class Command(BaseCommand):
    help = 'Create test revenue data for apps'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=6, help='Number of months of data to generate')

    def handle(self, *args, **options):
        months = options['months']
        apps = AppListing.objects.filter(status=AppListing.Status.ACTIVE)
        
        if not apps.exists():
            self.stdout.write(self.style.ERROR('No active apps found'))
            return
            
        self.stdout.write(f'Generating {months} months of revenue data for {apps.count()} apps')
        
        revenue_types = [choice[0] for choice in Revenue.RevenueType.choices]
        
        for app in apps:
            self.stdout.write(f'Generating revenue for {app.name}')
            
            # Generate monthly recurring revenue
            current_date = timezone.now()
            for month in range(months):
                # Calculate period dates
                period_end = current_date - timedelta(days=30 * month)
                period_start = period_end - timedelta(days=30)
                
                # Generate base monthly revenue (random between 100k and 1M)
                base_amount = Decimal(str(random.randint(100000, 1000000)))
                
                # Create subscription revenue
                Revenue.objects.create(
                    app=app,
                    amount=base_amount,
                    currency=Revenue.Currency.NGN,
                    source=Revenue.RevenueType.SUBSCRIPTION,
                    description='Monthly subscription revenue',
                    period_start=period_start,
                    period_end=period_end,
                    is_recurring=True,
                    recurring_interval='MONTHLY',
                    customer_count=random.randint(10, 100)
                )
                
                # Add some random one-time purchases
                for _ in range(random.randint(1, 5)):
                    amount = Decimal(str(random.randint(10000, 50000)))
                    Revenue.objects.create(
                        app=app,
                        amount=amount,
                        currency=Revenue.Currency.NGN,
                        source=random.choice(revenue_types),
                        description='One-time revenue',
                        period_start=period_start,
                        period_end=period_end,
                        customer_count=random.randint(1, 10)
                    )
            
        self.stdout.write(self.style.SUCCESS('Successfully generated test revenue data')) 
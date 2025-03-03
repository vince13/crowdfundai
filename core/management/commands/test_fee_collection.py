from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from core.models import AppListing, Investment, User
from core.services.payments import PaymentService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test platform fee collection by simulating complete funding of an app'

    def add_arguments(self, parser):
        parser.add_argument('app_id', type=int, help='ID of the app to test with')
        parser.add_argument('--amount', type=float, help='Optional: Specific amount to fund')

    def handle(self, *args, **options):
        try:
            # Get the app
            app = AppListing.objects.get(pk=options['app_id'])
            self.stdout.write(f"Testing fee collection for app: {app.name}")

            # Create test investor if needed
            investor, created = User.objects.get_or_create(
                email='test_investor@example.com',
                defaults={
                    'username': 'test_investor',
                    'role': User.Role.INVESTOR
                }
            )

            # Calculate funding amount
            amount = Decimal(str(options.get('amount', app.funding_goal)))
            
            # Create test investment
            investment = Investment.objects.create(
                investor=investor,
                app=app,
                amount_paid=amount,
                transaction_id=f'TEST-{timezone.now().strftime("%Y%m%d%H%M%S")}'
            )

            self.stdout.write(f"Created test investment of ₦{amount:,.2f}")

            # Process fee collection
            PaymentService.handle_funding_completion(app)

            self.stdout.write(self.style.SUCCESS(
                f"Successfully tested fee collection!\n"
                f"Platform Fee (5%): ₦{app.calculate_platform_fee():,.2f}\n"
                f"Developer Amount: ₦{amount - app.calculate_platform_fee():,.2f}"
            ))

        except AppListing.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"App with ID {options['app_id']} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}")) 
from django.contrib.auth.management.commands.createsuperuser import Command as SuperUserCommand
from django.core.management.base import CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import sys

class Command(SuperUserCommand):
    help = 'Create a superuser with email verification enabled'

    def handle(self, *args, **options):
        # Call the parent class's handle method to create the superuser
        super().handle(*args, **options)

        # Get the username that was just created
        username = options.get('username')
        if not username:
            # If username wasn't provided in options, it was prompted for
            # We need to get it from the last printed line
            if hasattr(self.stdout, 'getvalue'):
                output = self.stdout.getvalue().strip()
                # Extract username from the success message
                for line in output.split('\n'):
                    if 'Superuser created successfully' in line:
                        username = line.split()[0]
                        break

        if username:
            # Get the user model
            User = self.UserModel._default_manager.get_by_natural_key(username)
            
            # Set email verification to True
            User.is_email_verified = True
            User.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully enabled email verification for superuser "{username}"'
                )
            )
        else:
            raise CommandError('Could not determine the username of the created superuser')

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--password',
            help='Specifies the password for the superuser.',
        ) 

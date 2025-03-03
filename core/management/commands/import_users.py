from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import json
import base64
import sys

User = get_user_model()

class Command(BaseCommand):
    help = 'Import users from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to the JSON file containing user data')
        parser.add_argument('--skip-existing', action='store_true', help='Skip existing users instead of updating them')

    def handle(self, *args, **options):
        json_file = options['json_file']
        skip_existing = options['skip_existing']
        
        try:
            with open(json_file, 'r') as f:
                users_data = json.load(f)
            
            success_count = 0
            skip_count = 0
            error_count = 0
            
            for user_data in users_data:
                try:
                    email = user_data['email']
                    username = user_data['username']
                    
                    # Check if user exists
                    user_exists = User.objects.filter(email=email).exists()
                    
                    if user_exists and skip_existing:
                        self.stdout.write(
                            self.style.WARNING(f"Skipping existing user: {email}")
                        )
                        skip_count += 1
                        continue
                    
                    if user_exists:
                        user = User.objects.get(email=email)
                        self.stdout.write(
                            self.style.WARNING(f"Updating existing user: {email}")
                        )
                    else:
                        user = User(email=email, username=username)
                        self.stdout.write(
                            self.style.SUCCESS(f"Creating new user: {email}")
                        )
                    
                    # Update user fields
                    user.first_name = user_data.get('first_name', '')
                    user.last_name = user_data.get('last_name', '')
                    user.is_active = user_data.get('is_active', True)
                    user.is_staff = user_data.get('is_staff', False)
                    user.is_superuser = user_data.get('is_superuser', False)
                    user.role = user_data.get('role', 'USER')
                    user.bio = user_data.get('bio', '')
                    
                    # Set password hash if provided
                    if 'password' in user_data:
                        user.password = base64.b64decode(user_data['password'].encode()).decode()
                    
                    user.save()
                    
                    # Update permissions and groups
                    if 'permissions' in user_data:
                        user.user_permissions.set(user_data['permissions'])
                    if 'groups' in user_data:
                        user.groups.set(user_data['groups'])
                    
                    success_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing user {user_data.get('email')}: {str(e)}")
                    )
                    error_count += 1
                    continue
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nImport completed:\n"
                    f"Successfully imported/updated: {success_count}\n"
                    f"Skipped: {skip_count}\n"
                    f"Errors: {error_count}"
                )
            )
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f"File not found: {json_file}")
            )
            sys.exit(1)
        except json.JSONDecodeError:
            self.stdout.write(
                self.style.ERROR(f"Invalid JSON file: {json_file}")
            )
            sys.exit(1)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error: {str(e)}")
            )
            sys.exit(1) 
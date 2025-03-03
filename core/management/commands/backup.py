from django.core.management.base import BaseCommand
from django.conf import settings
from core.services.backup.backup_service import BackupService
import logging
import sys

logger = logging.getLogger('core.backup')

class Command(BaseCommand):
    help = 'Create system backups using BackupService'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'db', 'media', 'config'],
            help='Type of backup to create'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output messages'
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        quiet = options['quiet']

        try:
            if not quiet:
                self.stdout.write(f"Creating {backup_type} backup...")

            result = BackupService.create_backup(backup_type)

            if result['success']:
                if not quiet:
                    self.stdout.write(self.style.SUCCESS("Backup completed successfully!"))
                    for file_info in result['files']:
                        self.stdout.write(f"- {file_info['type']}: {file_info['filename']}")
                sys.exit(0)
            else:
                self.stderr.write(self.style.ERROR(f"Backup failed: {result['error']}"))
                sys.exit(1)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {str(e)}"))
            logger.error(f"Backup command failed: {str(e)}")
            sys.exit(1) 
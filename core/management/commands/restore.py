from django.core.management.base import BaseCommand
from django.conf import settings
from core.services.backup.backup_service import BackupService
import logging
import sys
import os

logger = logging.getLogger('core.backup')

class Command(BaseCommand):
    help = 'Restore system from backup using BackupService'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_path',
            type=str,
            help='Path to the backup file to restore from'
        )
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'db', 'media', 'config'],
            help='Type of backup to restore'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output messages'
        )

    def handle(self, *args, **options):
        backup_path = options['backup_path']
        backup_type = options['type']
        quiet = options['quiet']

        if not os.path.exists(backup_path):
            self.stderr.write(self.style.ERROR(f"Backup file not found: {backup_path}"))
            sys.exit(1)

        try:
            if not quiet:
                self.stdout.write(f"Restoring {backup_type} from {backup_path}...")

            result = BackupService.restore_backup(backup_path, backup_type)

            if result['success']:
                if not quiet:
                    self.stdout.write(self.style.SUCCESS(result['message']))
                sys.exit(0)
            else:
                self.stderr.write(self.style.ERROR(result['message']))
                sys.exit(1)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Restore failed: {str(e)}"))
            logger.error(f"Restore command failed: {str(e)}")
            sys.exit(1) 
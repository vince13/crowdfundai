import os
from datetime import datetime
import boto3
from django.conf import settings
import subprocess
import logging

logger = logging.getLogger('core')

class BackupService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        self.bucket_name = os.environ.get('AWS_BACKUP_BUCKET_NAME')
    
    def backup_database(self):
        """Create a database backup"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = 'backups/database'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Get database settings
            db_settings = settings.DATABASES['default']
            backup_file = f"{backup_dir}/db_backup_{timestamp}.sql"
            
            if db_settings['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL backup
                env = os.environ.copy()
                env['PGPASSWORD'] = db_settings['PASSWORD']
                
                cmd = [
                    'pg_dump',
                    '-h', db_settings['HOST'],
                    '-U', db_settings['USER'],
                    '-d', db_settings['NAME'],
                    '-f', backup_file
                ]
                
                subprocess.run(cmd, env=env, check=True)
                
            elif db_settings['ENGINE'] == 'django.db.backends.sqlite3':
                # SQLite backup
                import shutil
                shutil.copy2(db_settings['NAME'], backup_file)
            
            # Upload to S3
            if self.bucket_name:
                s3_key = f"database/db_backup_{timestamp}.sql"
                self.s3_client.upload_file(backup_file, self.bucket_name, s3_key)
                logger.info(f"Database backup uploaded to S3: {s3_key}")
            
            logger.info(f"Database backup completed: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            raise
    
    def backup_media_files(self):
        """Backup media files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = 'backups/media'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create archive of media files
            media_root = settings.MEDIA_ROOT
            archive_name = f"{backup_dir}/media_backup_{timestamp}.tar.gz"
            
            cmd = [
                'tar',
                '-czf',
                archive_name,
                '-C',
                os.path.dirname(media_root),
                os.path.basename(media_root)
            ]
            
            subprocess.run(cmd, check=True)
            
            # Upload to S3
            if self.bucket_name:
                s3_key = f"media/media_backup_{timestamp}.tar.gz"
                self.s3_client.upload_file(archive_name, self.bucket_name, s3_key)
                logger.info(f"Media backup uploaded to S3: {s3_key}")
            
            logger.info(f"Media backup completed: {archive_name}")
            return archive_name
            
        except Exception as e:
            logger.error(f"Media backup failed: {str(e)}")
            raise
    
    def perform_full_backup(self):
        """Perform both database and media backups"""
        try:
            db_backup = self.backup_database()
            media_backup = self.backup_media_files()
            
            return {
                'database_backup': db_backup,
                'media_backup': media_backup,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Full backup failed: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'status': 'failed',
                'error': str(e)
            }
    
    def list_backups(self):
        """List all available backups in S3"""
        if not self.bucket_name:
            return []
            
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='database/'
            )
            db_backups = [obj['Key'] for obj in response.get('Contents', [])]
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='media/'
            )
            media_backups = [obj['Key'] for obj in response.get('Contents', [])]
            
            return {
                'database_backups': db_backups,
                'media_backups': media_backups
            }
            
        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
            return [] 
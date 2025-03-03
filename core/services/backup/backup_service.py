import os
import shutil
import gzip
import json
import tarfile
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger('core.backup')

class BackupService:
    """Service for managing system backups with retention policy"""
    
    BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
    # Use retention days from settings or default to 7
    RETENTION_DAYS = getattr(settings, 'BACKUP_RETENTION_DAYS', 7)
    
    @classmethod
    def ensure_backup_dir(cls):
        """Ensure backup directories exist"""
        for subdir in ['db', 'media', 'config']:
            path = os.path.join(cls.BACKUP_DIR, subdir)
            os.makedirs(path, exist_ok=True)
    
    @classmethod
    def create_backup(cls, backup_type='full'):
        """Create a backup of the specified type and cleanup old backups"""
        result = {
            'success': False,
            'status': 'error',
            'files': [],
            'paths': [],
            'error': None
        }
        
        try:
            cls.ensure_backup_dir()
            
            if backup_type in ['full', 'db']:
                db_path = cls._backup_database()
                if db_path:
                    file_info = {
                        'type': 'database',
                        'path': db_path,
                        'filename': os.path.basename(db_path),
                        'size': os.path.getsize(db_path),
                        'created': datetime.fromtimestamp(os.path.getctime(db_path))
                    }
                    result['files'].append(file_info)
                    result['paths'].append(db_path)
                    cls.cleanup_old_backups('db')
            
            if backup_type in ['full', 'media']:
                media_path = cls._backup_media()
                if media_path:
                    file_info = {
                        'type': 'media',
                        'path': media_path,
                        'filename': os.path.basename(media_path),
                        'size': os.path.getsize(media_path),
                        'created': datetime.fromtimestamp(os.path.getctime(media_path))
                    }
                    result['files'].append(file_info)
                    result['paths'].append(media_path)
                    cls.cleanup_old_backups('media')
            
            if backup_type in ['full', 'config']:
                config_path = cls._backup_config()
                if config_path:
                    file_info = {
                        'type': 'config',
                        'path': config_path,
                        'filename': os.path.basename(config_path),
                        'size': os.path.getsize(config_path),
                        'created': datetime.fromtimestamp(os.path.getctime(config_path))
                    }
                    result['files'].append(file_info)
                    result['paths'].append(config_path)
                    cls.cleanup_old_backups('config')
            
            if result['files']:
                result['success'] = True
                result['status'] = 'success'
                result['error'] = None
                
                # If this was a full backup, ensure we don't exceed total limits
                if backup_type == 'full':
                    cls.cleanup_old_backups('db')
                    cls.cleanup_old_backups('media')
                    cls.cleanup_old_backups('config')
            
            return result
        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            result['error'] = str(e)
            return result
    
    @classmethod
    def _backup_database(cls):
        """Backup database to JSON format"""
        timestamp = cls._get_timestamp()
        temp_json = os.path.join(cls.BACKUP_DIR, 'db', f'temp_{timestamp}.json')
        final_path = os.path.join(cls.BACKUP_DIR, 'db', f'db_backup_{timestamp}.gz')
        
        try:
            # Dump database to temporary JSON file
            with open(temp_json, 'w') as f:
                call_command('dumpdata', stdout=f)
            
            # Compress JSON file
            with open(temp_json, 'rb') as f_in:
                with gzip.open(final_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return final_path
        finally:
            # Clean up temporary file
            if os.path.exists(temp_json):
                os.remove(temp_json)
    
    @classmethod
    def _backup_media(cls):
        """Backup media files to tar.gz format"""
        timestamp = cls._get_timestamp()
        filename = f'media_backup_{timestamp}.tar.gz'
        filepath = os.path.join(cls.BACKUP_DIR, 'media', filename)
        
        if not os.path.exists(settings.MEDIA_ROOT) or not os.listdir(settings.MEDIA_ROOT):
            # Create empty archive if no media files exist
            with gzip.open(filepath, 'wb') as f:
                f.write(b'')
        else:
            try:
                shutil.make_archive(
                    os.path.join(cls.BACKUP_DIR, 'media', f'media_backup_{timestamp}'),
                    'gztar',
                    settings.MEDIA_ROOT
                )
            except Exception as e:
                raise Exception(f'Media backup failed: {str(e)}')
        
        return filepath
    
    @classmethod
    def _backup_config(cls):
        """Backup configuration to JSON format"""
        timestamp = cls._get_timestamp()
        temp_json = os.path.join(cls.BACKUP_DIR, 'config', f'temp_{timestamp}.json')
        final_path = os.path.join(cls.BACKUP_DIR, 'config', f'config_backup_{timestamp}.gz')
        
        try:
            config = {
                'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
                'DATABASES': settings.DATABASES,
                'INSTALLED_APPS': settings.INSTALLED_APPS,
                'MIDDLEWARE': settings.MIDDLEWARE,
                'STATIC_URL': settings.STATIC_URL,
                'MEDIA_URL': settings.MEDIA_URL,
                'TIME_ZONE': settings.TIME_ZONE,
            }
            
            # Write config to temporary JSON file
            with open(temp_json, 'w') as f:
                json.dump(config, f, indent=4)
            
            # Compress JSON file
            with open(temp_json, 'rb') as f_in:
                with gzip.open(final_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return final_path
        finally:
            # Clean up temporary file
            if os.path.exists(temp_json):
                os.remove(temp_json)
    
    @classmethod
    def _get_timestamp(cls):
        """Get formatted timestamp for backup files"""
        return datetime.now().strftime('%Y%m%d_%H%M%S')
    
    @classmethod
    def restore_backup(cls, backup_path, backup_type='full'):
        """Restore from backup"""
        try:
            if backup_type in ['full', 'db']:
                cls._restore_database(backup_path)
            
            if backup_type in ['full', 'media']:
                cls._restore_media(backup_path)
            
            if backup_type in ['full', 'config']:
                cls._restore_config(backup_path)
            
            return {
                'success': True,
                'message': f'Successfully restored {backup_type} backup'
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            return {
                'success': False,
                'message': f'Restore failed: {str(e)}'
            }
    
    @classmethod
    def list_backups(cls):
        """List available backups"""
        cls.ensure_backup_dir()
        
        backups = {
            'database': [],
            'media': [],
            'config': []
        }
        
        # List database backups
        db_dir = os.path.join(cls.BACKUP_DIR, 'db')
        for file in os.listdir(db_dir):
            if file.startswith('db_backup_'):
                path = os.path.join(db_dir, file)
                backups['database'].append({
                    'filename': file,
                    'size': os.path.getsize(path),
                    'created': datetime.fromtimestamp(os.path.getctime(path))
                })
        
        # List media backups
        media_dir = os.path.join(cls.BACKUP_DIR, 'media')
        for file in os.listdir(media_dir):
            if file.startswith('media_backup_'):
                path = os.path.join(media_dir, file)
                backups['media'].append({
                    'filename': file,
                    'size': os.path.getsize(path),
                    'created': datetime.fromtimestamp(os.path.getctime(path))
                })
        
        # List config backups
        config_dir = os.path.join(cls.BACKUP_DIR, 'config')
        for file in os.listdir(config_dir):
            if file.startswith('config_backup_'):
                path = os.path.join(config_dir, file)
                backups['config'].append({
                    'filename': file,
                    'size': os.path.getsize(path),
                    'created': datetime.fromtimestamp(os.path.getctime(path))
                })
        
        return backups
    
    @classmethod
    def cleanup_old_backups(cls, backup_type):
        """Remove backups older than retention days"""
        try:
            directory = os.path.join(cls.BACKUP_DIR, backup_type)
            if not os.path.exists(directory):
                return
                
            # Get list of backup files sorted by creation time
            files = []
            for f in os.listdir(directory):
                path = os.path.join(directory, f)
                if os.path.isfile(path):
                    files.append((path, datetime.fromtimestamp(os.path.getctime(path))))
            
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove files older than retention days
            cutoff_date = datetime.now() - timedelta(days=cls.RETENTION_DAYS)
            for path, created in files:
                if created < cutoff_date:
                    os.remove(path)
                    logger.info(f"Removed old backup: {path}")
            
            return {
                'success': True,
                'message': f'Successfully cleaned up backups older than {cls.RETENTION_DAYS} days'
            }
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            return {
                'success': False,
                'message': f'Cleanup failed: {str(e)}'
            }
    
    @classmethod
    def verify_backup(cls, backup_path, backup_type):
        """Verify backup integrity"""
        try:
            if not os.path.exists(backup_path):
                return {
                    'status': 'error',
                    'message': f'Backup file not found: {backup_path}'
                }
            
            if backup_type == 'db':
                # Verify database backup
                with gzip.open(backup_path, 'rb') as f:
                    json.load(f)
            elif backup_type == 'media':
                # Verify media backup
                if not tarfile.is_tarfile(backup_path):
                    raise ValueError('Invalid tar file')
            elif backup_type == 'config':
                # Verify config backup
                with open(backup_path, 'r') as f:
                    json.load(f)
            
            return {
                'status': 'success',
                'message': f'Backup verification successful for {backup_type}'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Backup verification failed: {str(e)}'
            }

    @classmethod
    def _cleanup_old_backups(cls, backup_type):
        """Retain only the last 7 backups for the specified type"""
        try:
            directory = os.path.join(cls.BACKUP_DIR, backup_type)
            if not os.path.exists(directory):
                return
            
            # Get all backup files for the type
            files = []
            for file in os.listdir(directory):
                if file.startswith(f'{backup_type}_backup_'):
                    path = os.path.join(directory, file)
                    files.append({
                        'path': path,
                        'filename': file,
                        'created': datetime.fromtimestamp(os.path.getctime(path))
                    })
            
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x['created'], reverse=True)
            
            # Remove excess backups
            if len(files) > 7:
                for file in files[7:]:
                    try:
                        os.remove(file['path'])
                        logger.info(f"Removed old backup: {file['filename']}")
                    except Exception as e:
                        logger.error(f"Error deleting backup {file['filename']}: {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {str(e)}")
            return False

import os
import shutil
import json
import gzip
import pytest
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, datetime
from core.services.backup import BackupService
from core.models import User
from django.conf import settings
import tempfile

TEST_BACKUP_DIR = tempfile.mkdtemp()
TEST_MEDIA_ROOT = tempfile.mkdtemp()

def create_test_user(email, password, role):
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password=password,
        role=role
    )

@override_settings(BACKUP_DIR=TEST_BACKUP_DIR, MEDIA_ROOT=TEST_MEDIA_ROOT)
class BackupSystemTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create temporary test directories
        cls.test_dir = tempfile.mkdtemp()
        cls.test_media = tempfile.mkdtemp()
        # Override backup and media directories for testing
        BackupService.BACKUP_DIR = cls.test_dir
        settings.MEDIA_ROOT = cls.test_media

    @classmethod
    def tearDownClass(cls):
        # Clean up test directories
        shutil.rmtree(cls.test_dir, ignore_errors=True)
        shutil.rmtree(cls.test_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        """Set up test environment."""
        # Create test directories
        os.makedirs(os.path.join(TEST_BACKUP_DIR, 'db'), exist_ok=True)
        os.makedirs(os.path.join(TEST_BACKUP_DIR, 'media'), exist_ok=True)
        os.makedirs(os.path.join(TEST_BACKUP_DIR, 'config'), exist_ok=True)
        os.makedirs(TEST_MEDIA_ROOT, exist_ok=True)

        # Create test files in media directory
        with open(os.path.join(settings.MEDIA_ROOT, 'test.txt'), 'w') as f:
            f.write('test content')

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(TEST_BACKUP_DIR, ignore_errors=True)
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def test_backup_creation(self):
        """Test creating a full backup"""
        result = BackupService.create_backup()
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['files']), 3)  # db, media, config
        
        # Verify files exist and have content
        for file_info in result['files']:
            self.assertTrue(os.path.exists(file_info['path']))
            self.assertGreater(os.path.getsize(file_info['path']), 0)

    def test_backup_types(self):
        """Test different backup types"""
        # Test database backup
        db_result = BackupService.create_backup('db')
        self.assertTrue(db_result['success'])
        self.assertEqual(len(db_result['files']), 1)
        self.assertEqual(db_result['files'][0]['type'], 'database')
        self.assertTrue(os.path.exists(db_result['files'][0]['path']))
        
        # Test media backup
        media_result = BackupService.create_backup('media')
        self.assertTrue(media_result['success'])
        self.assertEqual(len(media_result['files']), 1)
        self.assertEqual(media_result['files'][0]['type'], 'media')
        self.assertTrue(os.path.exists(media_result['files'][0]['path']))
        
        # Test config backup
        config_result = BackupService.create_backup('config')
        self.assertTrue(config_result['success'])
        self.assertEqual(len(config_result['files']), 1)
        self.assertEqual(config_result['files'][0]['type'], 'config')
        self.assertTrue(os.path.exists(config_result['files'][0]['path']))

    def test_backup_recovery(self):
        """Test backup recovery process"""
        # Create a backup first
        result = BackupService.create_backup()
        self.assertTrue(result['success'])
        
        # Verify we can read the backup files
        for file_info in result['files']:
            path = file_info['path']
            backup_type = file_info['type']
            
            if backup_type == 'database':
                with gzip.open(path, 'rb') as f:
                    data = f.read().decode('utf-8')
                    self.assertTrue(len(data) > 0)
                    # Verify it's valid JSON
                    json.loads(data)
            elif backup_type == 'config':
                with gzip.open(path, 'rb') as f:
                    data = f.read().decode('utf-8')
                    self.assertTrue(len(data) > 0)
                    # Verify it's valid JSON
                    config = json.loads(data)
                    self.assertIn('INSTALLED_APPS', config)
                    self.assertIn('DATABASES', config)

    def test_backup_failure(self):
        """Test handling of backup failures"""
        # Set invalid backup directory
        invalid_dir = '/nonexistent/invalid'
        original_dir = BackupService.BACKUP_DIR
        BackupService.BACKUP_DIR = invalid_dir
        
        try:
            result = BackupService.create_backup()
            self.assertFalse(result['success'])
            self.assertEqual(result['status'], 'error')
            self.assertIsNotNone(result['error'])
        finally:
            BackupService.BACKUP_DIR = original_dir

    def test_empty_media_backup(self):
        """Test creating backup with empty media directory"""
        # Remove test files
        shutil.rmtree(settings.MEDIA_ROOT)
        os.makedirs(settings.MEDIA_ROOT)
        
        result = BackupService.create_backup('media')
        self.assertTrue(result['success'])
        self.assertEqual(len(result['files']), 1)
        
        # Verify empty archive was created
        media_file = result['files'][0]
        self.assertTrue(os.path.exists(media_file['path']))
        self.assertGreater(os.path.getsize(media_file['path']), 0)

    def test_backup_rotation(self):
        """Test backup rotation functionality"""
        # Create multiple backups
        backups = []
        for _ in range(3):
            result = BackupService.create_backup()
            self.assertTrue(result['success'])
            backups.extend(result['files'])
        
        # Verify backup file structure
        for backup in backups:
            self.assertTrue(os.path.exists(backup['path']))
            self.assertGreater(os.path.getsize(backup['path']), 0)

    def test_large_backup_handling(self):
        """Test handling of large backup files"""
        # Create some test data in media directory
        test_file = os.path.join(TEST_MEDIA_ROOT, 'large_file.txt')
        with open(test_file, 'w') as f:
            f.write('x' * 1024 * 1024)  # 1MB file
        
        result = BackupService.create_backup()
        self.assertTrue(result['success'])
        
        # Get the media backup file
        media_file = next(file_info for file_info in result['files'] if file_info['type'] == 'media')
        self.assertTrue(os.path.exists(media_file['path']))
        self.assertGreater(os.path.getsize(media_file['path']), 0)

    def test_corrupted_backup_handling(self):
        """Test handling of corrupted backup files"""
        # Create a backup
        result = BackupService.create_backup()
        self.assertTrue(result['success'])
        
        # Get the database backup file
        db_file = next(file_info for file_info in result['files'] if file_info['type'] == 'database')
        
        # Corrupt the backup file
        with open(db_file['path'], 'wb') as f:
            f.write(b'corrupted data')
        
        # Verify backup
        verify_result = BackupService.verify_backup(db_file['path'], 'db')
        self.assertEqual(verify_result['status'], 'error')
        self.assertIn('Backup verification failed', verify_result['message'])

    def test_backup_types_paths(self):
        """Test different backup types paths"""
        # Test database-only backup
        db_result = BackupService.create_backup(backup_type='db')
        self.assertTrue(db_result['success'])
        self.assertEqual(len(db_result['paths']), 1)
        self.assertTrue('db' in db_result['paths'][0])
        
        # Test media-only backup
        media_result = BackupService.create_backup(backup_type='media')
        self.assertTrue(media_result['success'])
        self.assertEqual(len(media_result['paths']), 1)
        self.assertTrue('media' in media_result['paths'][0])
        
        # Test config-only backup
        config_result = BackupService.create_backup(backup_type='config')
        self.assertTrue(config_result['success'])
        self.assertEqual(len(config_result['paths']), 1)
        self.assertTrue('config' in config_result['paths'][0])
        
        # Test full backup
        full_result = BackupService.create_backup(backup_type='full')
        self.assertTrue(full_result['success'])
        self.assertEqual(len(full_result['paths']), 3)

    def test_backup_content(self):
        """Test backup file contents"""
        result = BackupService.create_backup()
        self.assertTrue(result['success'])
        
        for file_info in result['files']:
            if 'db_backup' in file_info['path']:
                # Verify database backup is valid JSON
                with gzip.open(file_info['path'], 'rt') as f:
                    data = json.load(f)
                self.assertIsInstance(data, list)
            
            elif 'config_backup' in file_info['path']:
                # Verify config backup has required keys
                with gzip.open(file_info['path'], 'rt') as f:
                    config = json.load(f)
                self.assertIn('ALLOWED_HOSTS', config)
                self.assertIn('DATABASES', config)
                self.assertIn('INSTALLED_APPS', config) 
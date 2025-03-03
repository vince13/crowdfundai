from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
import os
import shutil
from datetime import datetime
from django.conf import settings
from ..services.backup.backup_service import BackupService

@staff_member_required
def create_backup(request):
    if request.method == 'POST':
        backup_type = request.POST.get('backup_type', 'full')
        try:
            backup_service = BackupService()
            result = backup_service.create_backup(backup_type)
            
            if result.get('success', False):
                messages.success(request, f"Successfully created {backup_type} backup: {result.get('filename', '')}")
            else:
                messages.error(request, result.get('error', 'Unknown error occurred'))
                
        except Exception as e:
            messages.error(request, f"An error occurred while creating backup: {str(e)}")
    
    return redirect('core:backup_dashboard')

@staff_member_required
def backup_dashboard(request):
    try:
        backup_service = BackupService()
        backups = backup_service.list_backups()
        return render(request, 'core/admin/backup/dashboard.html', {
            'backups': backups
        })
    except Exception as e:
        messages.error(request, f"Error loading backup dashboard: {str(e)}")
        return redirect('core:admin_dashboard')

@staff_member_required
def restore_backup(request, backup_type, filename):
    if request.method == 'POST':
        try:
            backup_service = BackupService()
            result = backup_service.restore_backup(backup_path=filename, backup_type=backup_type)
            
            if result.get('success', False):
                messages.success(request, f"Successfully restored {backup_type} backup")
            else:
                messages.error(request, result.get('error', 'Unknown error occurred'))
        except Exception as e:
            messages.error(request, f"An error occurred while restoring backup: {str(e)}")
    
    return redirect('core:backup_dashboard') 
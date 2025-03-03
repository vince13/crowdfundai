from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from ..models import SecurityAuditLog
from ..services.security import SecurityService
from ..decorators.admin_required import admin_required
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import json

@admin_required
def security_dashboard(request):
    """Security monitoring dashboard"""
    # Get recent audit logs
    recent_logs = SecurityAuditLog.objects.select_related('user').order_by('-timestamp')[:50]
    
    # Get statistics
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    
    stats = {
        'total_events': SecurityAuditLog.objects.count(),
        'recent_events': SecurityAuditLog.objects.filter(timestamp__gte=last_24h).count(),
        'failed_actions': SecurityAuditLog.objects.filter(
            status='failure',
            timestamp__gte=last_24h
        ).count(),
        'unique_ips': SecurityAuditLog.objects.filter(
            timestamp__gte=last_24h
        ).values('ip_address').distinct().count()
    }
    
    # Get event distribution
    event_distribution = SecurityAuditLog.objects.filter(
        timestamp__gte=last_24h
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return render(request, 'core/admin/security/dashboard.html', {
        'recent_logs': recent_logs,
        'stats': stats,
        'event_distribution': event_distribution
    })

@admin_required
def security_logs(request):
    """Detailed security logs view"""
    logs = SecurityAuditLog.objects.select_related('user').order_by('-timestamp')
    
    # Filter by date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        logs = logs.filter(timestamp__range=[start_date, end_date])
    
    # Filter by action type
    action_type = request.GET.get('action_type')
    if action_type:
        logs = logs.filter(action=action_type)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        logs = logs.filter(status=status)
    
    return render(request, 'core/admin/security/logs.html', {
        'logs': logs,
        'action_types': SecurityAuditLog.objects.values_list(
            'action', flat=True
        ).distinct()
    })

@admin_required
def security_settings(request):
    """Security settings management"""
    if request.method == 'POST':
        try:
            # Update security settings
            SecurityService.MIN_PASSWORD_LENGTH = int(request.POST.get('min_password_length', 8))
            SecurityService.PASSWORD_EXPIRY_DAYS = int(request.POST.get('password_expiry_days', 90))
            SecurityService.MAX_LOGIN_ATTEMPTS = int(request.POST.get('max_login_attempts', 5))
            
            messages.success(request, 'Security settings updated successfully')
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
    
    return render(request, 'core/admin/security/settings.html', {
        'current_settings': {
            'min_password_length': SecurityService.MIN_PASSWORD_LENGTH,
            'password_expiry_days': SecurityService.PASSWORD_EXPIRY_DAYS,
            'max_login_attempts': SecurityService.MAX_LOGIN_ATTEMPTS
        }
    }) 
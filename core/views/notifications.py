from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from ..models import Notification, NotificationPreference, NotificationTemplate
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from ..services.notifications import NotificationService
from django.contrib.auth.decorators import user_passes_test
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json
import asyncio
import time
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    unread_count = notifications.filter(is_read=False).count()
    
    return render(request, 'core/notifications/list.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })

@login_required
def mark_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    return redirect('core:notification_list')

@login_required
def mark_all_as_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    return redirect('core:notification_list')

@login_required
@require_POST
def delete_notification(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.delete()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

@login_required
@require_POST
def delete_all_notifications(request):
    request.user.notifications.all().delete()
    return JsonResponse({'status': 'success'})

@login_required
def get_unread_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def notification_preferences(request):
    preferences, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Debug logging
        print("\nPOST Data:", dict(request.POST))
        
        # Update preferences
        preferences.email_notifications = request.POST.get('email_notifications') == 'on'
        preferences.push_notifications = request.POST.get('push_notifications') == 'on'
        
        # Update type preferences - handle unchecked boxes explicitly
        preferences.investment_notifications = request.POST.get('investment_notifications') == 'on'
        preferences.price_alerts = request.POST.get('price_alerts') == 'on'
        preferences.system_notifications = request.POST.get('system_notifications') == 'on'
        preferences.milestone_notifications = request.POST.get('milestone_notifications') == 'on'
        preferences.app_update_notifications = request.POST.get('app_update_notifications') == 'on'
        preferences.funding_goal_notifications = request.POST.get('funding_goal_notifications') == 'on'
        preferences.dividend_notifications = request.POST.get('dividend_notifications') == 'on'
        preferences.security_notifications = request.POST.get('security_notifications') == 'on'
        preferences.maintenance_notifications = request.POST.get('maintenance_notifications') == 'on'
        preferences.news_notifications = request.POST.get('news_notifications') == 'on'
        preferences.app_approval_notifications = request.POST.get('app_approval_notifications') == 'on'
        
        # Update price alert threshold
        try:
            threshold = Decimal(request.POST.get('price_alert_threshold', '5.00'))
            preferences.price_alert_threshold = threshold
        except InvalidOperation:
            messages.error(request, "Invalid price alert threshold value")
        
        # Save all changes
        preferences.save()
        
        # Debug logging
        print("\nResulting Preferences:")
        print(f"- email_notifications: {preferences.email_notifications}")
        print(f"- push_notifications: {preferences.push_notifications}")
        print(f"- price_alerts: {preferences.price_alerts}")
        print(f"- app_approval_notifications: {preferences.app_approval_notifications}")
        print(f"- POST data for price_alerts: {request.POST.get('price_alerts')}")
        print(f"- POST data for app_approval_notifications: {request.POST.get('app_approval_notifications')}")
        
        messages.success(request, "Notification preferences updated successfully")
        return redirect('core:notification_preferences')
    
    return render(request, 'core/notifications/preferences.html', {
        'preferences': preferences,
        'notification_types': Notification.Type.choices
    })

@login_required
def test_notification(request):
    """Test endpoint to send a notification to the current user."""
    try:
        # Create a test notification
        notification = NotificationService.create_notification(
            user=request.user,
            title="Test Notification",
            message="This is a test notification sent via WebSocket.",
            notification_type="SYSTEM",
            link="/notifications/"
        )
        
        # Send the notification via WebSocket
        NotificationService.send_notification(notification)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Test notification sent successfully',
            'notification': {
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'link': notification.link,
                'created_at': notification.created_at.isoformat()
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def test_all_notifications(request):
    if request.method == 'POST':
        test_type = request.POST.get('test_type')
        
        try:
            if test_type == 'email':
                # Test email notification
                NotificationService.send_email_notification(
                    user=request.user,
                    subject="Test Email Notification",
                    template='core/emails/notification.html',
                    context={
                        'title': 'Test Email',
                        'message': 'This is a test email notification.',
                        'link': '/dashboard/'
                    }
                )
                messages.success(request, "Test email sent!")
                
            elif test_type == 'push':
                # Ensure notification preferences exist
                preferences, created = NotificationPreference.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'email_notifications': True,
                        'push_notifications': True
                    }
                )
                
                # Test push notification using NotificationService instead
                NotificationService.send_push_notification(
                    user=request.user,
                    title="Test Push Notification",
                    message="This is a test push notification."
                )
                messages.success(request, "Test push notification sent!")
                
            elif test_type == 'digest':
                # Test notification digest
                NotificationService.send_daily_digest()
                messages.success(request, "Test digest sent!")
                
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return render(request, 'core/notifications/test_all.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def manage_templates(request):
    """View for managing notification templates"""
    templates = NotificationTemplate.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            template = NotificationTemplate.objects.create(
                name=request.POST.get('name'),
                type=request.POST.get('type'),
                title_template=request.POST.get('title_template'),
                message_template=request.POST.get('message_template'),
                link_template=request.POST.get('link_template', '')
            )
            messages.success(request, f'Template "{template.name}" created successfully!')
            
        elif action == 'update':
            template_id = request.POST.get('template_id')
            template = NotificationTemplate.objects.get(id=template_id)
            template.name = request.POST.get('name')
            template.type = request.POST.get('type')
            template.title_template = request.POST.get('title_template')
            template.message_template = request.POST.get('message_template')
            template.link_template = request.POST.get('link_template', '')
            template.is_active = request.POST.get('is_active') == 'on'
            template.save()
            messages.success(request, f'Template "{template.name}" updated successfully!')
            
        elif action == 'delete':
            template_id = request.POST.get('template_id')
            NotificationTemplate.objects.filter(id=template_id).delete()
            messages.success(request, 'Template deleted successfully!')
        
        return redirect('core:manage_templates')
    
    return render(request, 'core/notifications/manage_templates.html', {
        'templates': templates,
        'notification_types': Notification.Type.choices
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def template_detail(request, pk):
    """API endpoint for getting template details"""
    try:
        template = NotificationTemplate.objects.get(pk=pk)
        return JsonResponse({
            'id': template.id,
            'name': template.name,
            'type': template.type,
            'title_template': template.title_template,
            'message_template': template.message_template,
            'link_template': template.link_template,
            'is_active': template.is_active
        })
    except NotificationTemplate.DoesNotExist:
        return JsonResponse({'error': 'Template not found'}, status=404) 

@login_required
def recent_notifications(request):
    """Get recent notifications for the dropdown"""
    notifications = request.user.notifications.all()[:5]  # Get last 5 notifications
    
    return JsonResponse({
        'notifications': [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    }) 

@login_required
@csrf_exempt  # SSE connections don't need CSRF
@require_http_methods(["GET"])  # Only allow GET requests
def notification_stream(request):
    """Server-Sent Events endpoint for real-time notifications"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        response = StreamingHttpResponse(
            'data: {"error": "Authentication required"}\n\n',
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        return response

    def event_stream():
        last_check = None
        
        while True:
            try:
                # Verify user is still authenticated
                if not request.user.is_authenticated:
                    yield 'data: {"error": "Session expired"}\n\n'
                    break

                # Get new notifications
                notifications = Notification.objects.filter(
                    user=request.user,
                    is_read=False
                )
                if last_check:
                    notifications = notifications.filter(created_at__gt=last_check)
                
                if notifications.exists():
                    # Convert notifications to list of dicts
                    data = [{
                        'id': n.id,
                        'message': n.message,
                        'type': n.type,
                        'created_at': n.created_at.isoformat()
                    } for n in notifications]
                    
                    # Send notifications as SSE
                    yield f"data: {json.dumps(data)}\n\n"
                
                # Send heartbeat to keep connection alive
                else:
                    yield ': heartbeat\n\n'
                
                last_check = timezone.now()
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    
    # Set CORS headers only if needed
    if request.META.get('HTTP_ORIGIN'):
        allowed_origins = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'https://www.fundafrica.net',
            'https://fundafrica.net'
        ]
        origin = request.META['HTTP_ORIGIN']
        if origin in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
    
    return response 
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from ..services.monitoring.metrics import SystemMetricsService
from ..services.monitoring.alerts import AlertService
import csv
import json
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views import View

def is_admin(user):
    return user.is_authenticated and user.role == 'ADMIN'

@user_passes_test(is_admin)
def get_metrics(request):
    """API endpoint for real-time metrics"""
    metrics_service = SystemMetricsService()
    
    metrics = {
        'system_metrics': metrics_service.get_system_metrics(),
        'database_metrics': metrics_service.get_database_metrics(),
        'response_metrics': metrics_service.get_response_metrics(),
        'error_metrics': metrics_service.get_error_metrics()
    }
    
    # Check for alerts
    alerts = AlertService.check_thresholds(metrics)
    metrics['alerts'] = alerts
    
    return JsonResponse(metrics)

@user_passes_test(is_admin)
def update_thresholds(request):
    """Update alert thresholds"""
    if request.method == 'POST':
        try:
            thresholds = json.loads(request.body)
            AlertService.update_thresholds(thresholds)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@user_passes_test(is_admin)
def export_metrics(request):
    """Export metrics to CSV"""
    metrics_service = SystemMetricsService()
    
    # Collect all metrics
    metrics = {
        'system_metrics': metrics_service.get_system_metrics(),
        'database_metrics': metrics_service.get_database_metrics(),
        'response_metrics': metrics_service.get_response_metrics(),
        'error_metrics': metrics_service.get_error_metrics()
    }
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="metrics_export_{timestamp}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Category', 'Metric', 'Value', 'Unit'])
    
    # System Metrics
    for key, value in metrics['system_metrics'].items():
        if key != 'timestamp':
            unit = '%' if 'usage' in key else ''
            writer.writerow(['System', key, value, unit])
    
    # Database Metrics
    for key, value in metrics['database_metrics'].items():
        if key == 'database_size_bytes':
            writer.writerow(['Database', 'size', value, 'bytes'])
        elif key == 'active_connections':
            writer.writerow(['Database', key, value, 'connections'])
    
    # Response Metrics
    for key, value in metrics['response_metrics'].items():
        if key != 'endpoint_metrics':
            writer.writerow(['Response', key, value, 'seconds' if 'time' in key else 'count'])
    
    # Error Metrics
    for key, value in metrics['error_metrics'].items():
        unit = '%' if key == 'error_rate' else 'count'
        writer.writerow(['Error', key, value, unit])
    
    return response

@method_decorator(staff_member_required, name='dispatch')
class MonitoringDashboardView(TemplateView):
    template_name = 'core/monitoring/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        metrics_service = SystemMetricsService()
        alert_service = AlertService()
        
        system_metrics = metrics_service.get_system_metrics()
        db_metrics = metrics_service.get_database_metrics()
        response_metrics = metrics_service.get_response_metrics()
        error_metrics = metrics_service.get_error_metrics()
        
        # Convert metrics to match alert service expectations
        alert_metrics = {
            'cpu_usage': system_metrics['cpu_usage'],
            'memory_usage': system_metrics['memory_usage'],
            'disk_usage': system_metrics['disk_usage'],
            'error_rate': error_metrics['error_rate'],
            'response_time': response_metrics['avg_response_time']
        }
        
        alerts = alert_service.check_thresholds(alert_metrics)
        
        context.update({
            'system_metrics': system_metrics,
            'db_metrics': db_metrics,
            'response_metrics': response_metrics,
            'error_metrics': error_metrics,
            'alerts': alerts,
            'thresholds': alert_service.get_thresholds()
        })
        return context

@method_decorator(staff_member_required, name='dispatch')
class UpdateThresholdsView(View):
    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        try:
            thresholds = json.loads(request.body)
            alert_service = AlertService()
            alert_service.update_thresholds(thresholds)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

@method_decorator(staff_member_required, name='dispatch')
class ExportMetricsView(View):
    def get(self, request, *args, **kwargs):
        metrics_service = SystemMetricsService()
        
        # Collect all metrics
        system_metrics = metrics_service.get_system_metrics()
        db_metrics = metrics_service.get_database_metrics()
        response_metrics = metrics_service.get_response_metrics()
        error_metrics = metrics_service.get_error_metrics()
        
        # Prepare response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Metric Type', 'Metric Name', 'Value', 'Unit'])
        
        # System Metrics
        writer.writerow(['System', 'CPU Usage', system_metrics['cpu_percent'], '%'])
        writer.writerow(['System', 'Memory Usage', system_metrics['memory_percent'], '%'])
        writer.writerow(['System', 'Disk Usage', system_metrics['disk_percent'], '%'])
        
        # Database Metrics
        writer.writerow(['Database', 'Active Connections', db_metrics['active_connections'], 'connections'])
        writer.writerow(['Database', 'Database Size', db_metrics['database_size'], 'bytes'])
        
        # Response Metrics
        writer.writerow(['Response', 'Average Response Time', response_metrics['avg_response_time'], 'seconds'])
        writer.writerow(['Response', 'Max Response Time', response_metrics['max_response_time'], 'seconds'])
        writer.writerow(['Response', 'Min Response Time', response_metrics['min_response_time'], 'seconds'])
        
        # Error Metrics
        writer.writerow(['Error', 'Error Rate', error_metrics['error_rate'], '%'])
        writer.writerow(['Error', 'Total Requests', error_metrics['total_requests'], 'requests'])
        writer.writerow(['Error', 'Error Count', error_metrics['error_count'], 'errors'])
        
        return response 
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from ..services.health import HealthCheckService
from ..decorators.admin_required import admin_required

@admin_required
def health_dashboard(request):
    """View for health check dashboard"""
    health_status = HealthCheckService.run_all_checks()
    return render(request, 'core/admin/health.html', {
        'health_status': health_status
    })

@admin_required
def health_check_api(request):
    """API endpoint for health status"""
    health_status = HealthCheckService.run_all_checks()
    return JsonResponse(health_status) 
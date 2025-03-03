from django.shortcuts import redirect
from django.urls import resolve
from django.contrib import messages

class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_paths = [
            'admin_dashboard',
            'monitoring_dashboard',
            'health_dashboard',
            'health_check_api',
            'get_metrics',
            # Add other admin paths as needed
        ]

    def __call__(self, request):
        url_name = resolve(request.path_info).url_name
        
        if url_name in self.admin_paths:
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('core:login')
            
            if not request.user.role == 'ADMIN':
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('core:dashboard')

        return self.get_response(request) 
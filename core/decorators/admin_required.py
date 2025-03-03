from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('core:login')
            
        if not request.user.role == 'ADMIN':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('core:dashboard')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view 
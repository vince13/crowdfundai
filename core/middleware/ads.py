from django.shortcuts import redirect
from django.contrib import messages

class DisableAdsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the URL starts with /ads/
        if request.path.startswith('/ads/'):
            messages.info(request, 'Advertisement functionality is temporarily disabled.')
            return redirect('core:home')
        return self.get_response(request) 
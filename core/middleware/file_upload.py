import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden

class FileUploadMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.FILES:
            for uploaded_file in request.FILES.values():
                # Check file size
                if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
                    return HttpResponseForbidden(
                        f'File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE/1024/1024}MB'
                    )
                
                # Check file extension
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
                    return HttpResponseForbidden(
                        f'File type {ext} is not allowed. Allowed types: {", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS)}'
                    )

        response = self.get_response(request)
        return response 
from django.core.management.commands.runserver import Command as RunserverCommand

class Command(RunserverCommand):
    def get_handler(self, *args, **options):
        """
        Force HTTP for development server
        """
        handler = super().get_handler(*args, **options)
        
        # Monkey patch the handler to always return False for is_secure()
        def _get_response(request):
            request.is_secure = lambda: False
            return handler._get_response(request)
            
        handler._get_response = _get_response
        return handler 
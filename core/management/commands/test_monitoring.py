from django.core.management.base import BaseCommand
from core.services.monitoring import SystemMetricsService
from django.core.cache import cache
import time

class Command(BaseCommand):
    help = 'Test the monitoring system by generating some load and checking metrics'

    def handle(self, *args, **options):
        metrics_service = SystemMetricsService()
        
        self.stdout.write('Testing monitoring system...')
        
        # Clear existing metrics
        cache.delete('response_times')
        cache.delete('error_count')
        cache.delete('request_count')
        
        # Generate some test data
        for i in range(10):
            # Simulate requests
            cache.set('request_count', i + 1, timeout=3600)
            
            # Simulate response times (between 0.1 and 0.5 seconds)
            response_times = cache.get('response_times', [])
            response_times.append(0.1 + (i * 0.05))
            cache.set('response_times', response_times, timeout=3600)
            
            # Simulate some errors
            if i % 3 == 0:  # Every third request fails
                error_count = cache.get('error_count', 0)
                cache.set('error_count', error_count + 1, timeout=3600)
            
            time.sleep(1)  # Wait a second between simulated requests
            
            # Get and display current metrics
            system_metrics = metrics_service.get_system_metrics()
            response_metrics = metrics_service.get_response_metrics()
            error_metrics = metrics_service.get_error_metrics()
            
            self.stdout.write(f'\nIteration {i + 1}:')
            self.stdout.write(f'System Metrics: {system_metrics}')
            self.stdout.write(f'Response Metrics: {response_metrics}')
            self.stdout.write(f'Error Metrics: {error_metrics}') 
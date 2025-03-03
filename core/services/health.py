from django.db import connections
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import redis
import requests
import psutil
import logging

logger = logging.getLogger('core.monitoring')

class HealthCheckService:
    @staticmethod
    def check_database():
        """Check database connectivity and performance"""
        try:
            for db_name in connections:
                cursor = connections[db_name].cursor()
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if row is None:
                    raise Exception(f"Database {db_name} check failed")
            return {
                'status': 'healthy',
                'message': 'All database connections are working'
            }
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Database check failed: {str(e)}'
            }

    @staticmethod
    def check_cache():
        """Verify cache system is working"""
        try:
            test_key = "health_check_test"
            test_value = "test_value"
            cache.set(test_key, test_value, 10)
            retrieved_value = cache.get(test_key)
            
            if retrieved_value != test_value:
                raise Exception("Cache retrieval failed")
                
            return {
                'status': 'healthy',
                'message': 'Cache system is working properly'
            }
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Cache check failed: {str(e)}'
            }

    @staticmethod
    def check_redis():
        """Check Redis connection for WebSocket"""
        try:
            # Get Redis host and port from settings
            redis_config = settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0]
            host, port = redis_config  # Unpack the tuple
            
            # Create Redis client
            redis_client = redis.Redis(
                host=host,
                port=port,
                socket_timeout=5,  # Add timeout
                decode_responses=True  # Decode responses to strings
            )
            
            # Test connection
            redis_client.ping()
            
            return {
                'status': 'healthy',
                'message': 'Redis connection is working'
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Redis check failed: {str(e)}'
            }

    @staticmethod
    def check_paystack():
        """Check Paystack API connectivity"""
        try:
            # Make a request to Paystack's ping endpoint
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            response = requests.get(
                'https://api.paystack.co/ping',
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            
            return {
                'status': 'healthy',
                'message': 'Paystack API is accessible'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Paystack check failed: {str(e)}'
            }

    @staticmethod
    def check_system_resources():
        """Check system resource availability"""
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = 'healthy'
            messages = []
            
            if cpu_usage > 90:
                status = 'warning'
                messages.append(f'High CPU usage: {cpu_usage}%')
            
            if memory.percent > 90:
                status = 'warning'
                messages.append(f'High memory usage: {memory.percent}%')
            
            if disk.percent > 90:
                status = 'warning'
                messages.append(f'Low disk space: {disk.free / (1024**3):.2f} GB free')
            
            return {
                'status': status,
                'message': ' | '.join(messages) if messages else 'System resources are normal',
                'details': {
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory.percent,
                    'disk_usage': disk.percent
                }
            }
        except Exception as e:
            logger.error(f"System resources check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'System resources check failed: {str(e)}'
            }

    @staticmethod
    def run_all_checks():
        """Run all health checks"""
        results = {
            'database': HealthCheckService.check_database(),
            'cache': HealthCheckService.check_cache(),
            'redis': HealthCheckService.check_redis(),
            'paystack': HealthCheckService.check_paystack(),
            'system': HealthCheckService.check_system_resources()
        }
        
        # Determine overall status
        overall_status = 'healthy'
        if any(check['status'] == 'unhealthy' for check in results.values()):
            overall_status = 'unhealthy'
        elif any(check['status'] == 'warning' for check in results.values()):
            overall_status = 'warning'
            
        return {
            'status': overall_status,
            'timestamp': timezone.now(),
            'checks': results
        } 
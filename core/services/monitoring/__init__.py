from .metrics import SystemMetricsService
from datetime import datetime, timedelta
from django.core.cache import cache

class PerformanceMonitor:
    @staticmethod
    def monitor_resource_usage():
        """Get current system metrics"""
        metrics = SystemMetricsService.get_system_metrics()
        metrics.update(SystemMetricsService.get_database_metrics())
        metrics.update(SystemMetricsService.get_response_metrics())
        metrics.update(SystemMetricsService.get_error_metrics())
        metrics.update(SystemMetricsService.get_cache_metrics())
        return metrics

    @staticmethod
    def get_historical_metrics(days=1):
        """Get historical metrics from cache"""
        historical_metrics = cache.get('historical_metrics', [])
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # Filter metrics within the specified time range
        filtered_metrics = [
            metric for metric in historical_metrics 
            if datetime.fromisoformat(metric['timestamp']) > cutoff_time
        ]
        
        return filtered_metrics

    @staticmethod
    def get_alerts():
        """Get system alerts based on metrics"""
        metrics = PerformanceMonitor.monitor_resource_usage()
        alerts = []
        
        # CPU usage alert
        if metrics['cpu_usage'] > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High CPU usage: {metrics["cpu_usage"]}%'
            })
        
        # Memory usage alert
        if metrics['memory_usage'] > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High memory usage: {metrics["memory_usage"]}%'
            })
        
        # Disk usage alert
        if metrics['disk_usage'] > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High disk usage: {metrics["disk_usage"]}%'
            })
        
        # Error rate alert
        if metrics.get('error_rate', 0) > 5:
            alerts.append({
                'level': 'error',
                'message': f'High error rate: {metrics["error_rate"]}%'
            })
        
        return alerts

__all__ = ['SystemMetricsService', 'PerformanceMonitor']
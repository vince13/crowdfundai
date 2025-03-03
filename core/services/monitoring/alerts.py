from django.core.cache import cache
from django.conf import settings

class AlertService:
    """Service for managing monitoring alerts and thresholds"""
    
    CACHE_KEY = 'monitoring_thresholds'
    DEFAULT_THRESHOLDS = {
        'cpu_usage': 80,  # 80% CPU usage
        'memory_usage': 85,  # 85% memory usage
        'disk_usage': 90,  # 90% disk usage
        'error_rate': 5,  # 5% error rate
        'response_time': 2.0  # 2 seconds response time
    }
    
    def __init__(self):
        """Initialize the alert service with default thresholds if not set"""
        if not cache.get(self.CACHE_KEY):
            cache.set(self.CACHE_KEY, self.DEFAULT_THRESHOLDS, timeout=None)
    
    def get_thresholds(self):
        """Get current alert thresholds"""
        return cache.get(self.CACHE_KEY, self.DEFAULT_THRESHOLDS)
    
    def update_thresholds(self, thresholds):
        """Update alert thresholds
        
        Args:
            thresholds (dict): Dictionary of threshold values to update
        """
        current_thresholds = self.get_thresholds()
        current_thresholds.update(thresholds)
        cache.set(self.CACHE_KEY, current_thresholds, timeout=None)
    
    def check_thresholds(self, metrics):
        """Check current metrics against thresholds
        
        Args:
            metrics (dict): Dictionary of current metric values
            
        Returns:
            list: List of alert dictionaries for metrics exceeding thresholds
        """
        thresholds = self.get_thresholds()
        alerts = []
        
        # CPU Usage Alert
        if metrics.get('cpu_usage') > thresholds['cpu_usage']:
            alerts.append({
                'level': 'danger',
                'metric': 'CPU Usage',
                'message': 'CPU usage is critically high',
                'value': f"{metrics['cpu_usage']}%",
                'threshold': f"{thresholds['cpu_usage']}%"
            })
        
        # Memory Usage Alert
        if metrics.get('memory_usage') > thresholds['memory_usage']:
            alerts.append({
                'level': 'danger',
                'metric': 'Memory Usage',
                'message': 'Memory usage is critically high',
                'value': f"{metrics['memory_usage']}%",
                'threshold': f"{thresholds['memory_usage']}%"
            })
        
        # Disk Usage Alert
        if metrics.get('disk_usage') > thresholds['disk_usage']:
            alerts.append({
                'level': 'danger',
                'metric': 'Disk Usage',
                'message': 'Disk usage is critically high',
                'value': f"{metrics['disk_usage']}%",
                'threshold': f"{thresholds['disk_usage']}%"
            })
        
        # Error Rate Alert
        if metrics.get('error_rate') > thresholds['error_rate']:
            alerts.append({
                'level': 'danger',
                'metric': 'Error Rate',
                'message': 'Error rate is above threshold',
                'value': f"{metrics['error_rate']}%",
                'threshold': f"{thresholds['error_rate']}%"
            })
        
        # Response Time Alert
        if metrics.get('response_time') > thresholds['response_time']:
            alerts.append({
                'level': 'warning',
                'metric': 'Response Time',
                'message': 'Response time is above threshold',
                'value': f"{metrics['response_time']:.2f}s",
                'threshold': f"{thresholds['response_time']:.2f}s"
            })
        
        return alerts
    
    def get_warning_level(self, metric_value, threshold):
        """Determine warning level based on how far the metric is above the threshold
        
        Args:
            metric_value (float): Current metric value
            threshold (float): Threshold value
            
        Returns:
            str: Warning level ('warning', 'danger')
        """
        if metric_value >= threshold * 1.5:
            return 'danger'
        elif metric_value >= threshold:
            return 'warning'
        return None 
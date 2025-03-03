import pytest
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from django.test import override_settings
from core.services.monitoring.metrics import SystemMetricsService
from core.services.monitoring.alerts import AlertService
from datetime import timedelta
import json

@pytest.mark.django_db
class TestMonitoringSystem:
    @pytest.fixture(autouse=True)
    def setup(self, client, admin_user):
        """Set up test data"""
        self.client = client
        self.admin_user = admin_user
        self.admin_user.is_staff = True
        self.admin_user.save()
        
        self.metrics_service = SystemMetricsService()
        self.alert_service = AlertService()
        
        # Clear cache before each test
        cache.clear()

    def test_system_metrics_collection(self):
        """Test system metrics collection"""
        metrics = self.metrics_service.get_system_metrics()
        
        # Check required metrics exist
        assert 'cpu_usage' in metrics
        assert 'memory_usage' in metrics
        assert 'disk_usage' in metrics
        assert 'timestamp' in metrics
        
        # Validate metric values
        assert isinstance(metrics['cpu_usage'], (int, float))
        assert isinstance(metrics['memory_usage'], (int, float))
        assert isinstance(metrics['disk_usage'], (int, float))
        
        # Check value ranges
        assert 0 <= metrics['cpu_usage'] <= 100
        assert 0 <= metrics['memory_usage'] <= 100
        assert 0 <= metrics['disk_usage'] <= 100

    def test_high_load_metrics_collection(self):
        """Test metrics collection under high load"""
        # Simulate high load by making multiple concurrent requests
        results = []
        for _ in range(10):
            metrics = self.metrics_service.get_system_metrics()
            results.append(metrics)
        
        # Verify all requests returned valid data
        for metrics in results:
            assert all(key in metrics for key in ['cpu_usage', 'memory_usage', 'disk_usage'])
            assert all(0 <= metrics[key] <= 100 for key in ['cpu_usage', 'memory_usage', 'disk_usage'])

    def test_metrics_caching(self):
        """Test metrics caching behavior"""
        # Get initial metrics
        initial_metrics = self.metrics_service.get_system_metrics()
        
        # Get metrics again immediately
        cached_metrics = self.metrics_service.get_system_metrics()
        
        # Should return cached values
        assert initial_metrics == cached_metrics
        
        # Wait for cache to expire
        cache.clear()
        
        # Get fresh metrics
        fresh_metrics = self.metrics_service.get_system_metrics()
        assert fresh_metrics['timestamp'] != initial_metrics['timestamp']

    def test_alert_threshold_edge_cases(self):
        """Test alert threshold edge cases"""
        # Test threshold at exactly 100%
        self.alert_service.update_thresholds({
            'cpu_usage': 100,
            'memory_usage': 100
        })
        
        alerts = self.alert_service.check_thresholds({
            'cpu_usage': 100,
            'memory_usage': 100
        })
        assert len(alerts) == 0  # Should not trigger at exactly 100%
        
        # Test threshold at 0%
        self.alert_service.update_thresholds({
            'cpu_usage': 0,
            'memory_usage': 0
        })
        
        alerts = self.alert_service.check_thresholds({
            'cpu_usage': 0,
            'memory_usage': 0
        })
        assert len(alerts) == 0  # Should not trigger at exactly 0%

    def test_metric_data_validation(self):
        """Test validation of metric data"""
        with pytest.raises(ValueError):
            self.metrics_service.validate_metrics({
                'cpu_usage': -1,  # Invalid negative value
                'memory_usage': 50
            })
        
        with pytest.raises(ValueError):
            self.metrics_service.validate_metrics({
                'cpu_usage': 101,  # Invalid value over 100
                'memory_usage': 50
            })

    def test_alert_aggregation(self):
        """Test aggregation of multiple alerts"""
        # Create multiple alerts
        test_metrics = {
            'cpu_usage': 95,
            'memory_usage': 90,
            'disk_usage': 85
        }
        
        self.alert_service.update_thresholds({
            'cpu_usage': 80,
            'memory_usage': 80,
            'disk_usage': 80
        })
        
        alerts = self.alert_service.check_thresholds(test_metrics)
        
        # Verify alert aggregation
        assert len(alerts) == 3
        assert all('level' in alert for alert in alerts)
        assert all('metric' in alert for alert in alerts)
        
        # Test alert priority ordering
        alert_levels = [alert['level'] for alert in alerts]
        assert alert_levels == sorted(alert_levels, reverse=True)

    def test_metric_history_tracking(self):
        """Test tracking of metric history"""
        # Record metrics at different times
        for _ in range(5):
            metrics = self.metrics_service.get_system_metrics()
            self.metrics_service.record_metric_history(metrics)
        
        # Get metric history
        history = self.metrics_service.get_metric_history()
        
        assert len(history) == 5
        assert all('timestamp' in entry for entry in history)
        assert all('cpu_usage' in entry for entry in history)

    def test_alert_notification_throttling(self):
        """Test alert notification throttling"""
        # Simulate multiple alerts in quick succession
        for _ in range(10):
            self.alert_service.process_alert({
                'level': 'critical',
                'metric': 'cpu_usage',
                'value': 95
            })
        
        # Check that notifications were throttled
        notification_count = self.alert_service.get_notification_count()
        assert notification_count < 10  # Should be throttled

    def test_system_health_check(self):
        """Test system health check functionality"""
        # Test normal conditions
        health_status = self.metrics_service.check_system_health()
        assert health_status['status'] == 'healthy'
        
        # Simulate unhealthy conditions
        with override_settings(DATABASES={'default': {'HOST': 'invalid_host'}}):
            health_status = self.metrics_service.check_system_health()
            assert health_status['status'] == 'unhealthy'
            assert 'database' in health_status['issues']

    def test_metric_data_export(self):
        """Test metric data export functionality"""
        # Record some test metrics
        test_metrics = []
        for _ in range(5):
            metrics = self.metrics_service.get_system_metrics()
            test_metrics.append(metrics)
            self.metrics_service.record_metric_history(metrics)
        
        # Export metrics
        export_data = self.metrics_service.export_metrics()
        
        # Verify export format
        assert isinstance(export_data, str)
        exported_metrics = json.loads(export_data)
        assert len(exported_metrics) == 5
        assert all(required_key in exported_metrics[0] 
                  for required_key in ['cpu_usage', 'memory_usage', 'disk_usage', 'timestamp']) 
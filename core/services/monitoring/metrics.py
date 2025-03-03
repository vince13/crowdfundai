import psutil
import time
from datetime import datetime, timedelta
from django.db import connection
from django.core.cache import cache
from typing import Dict, Any
import os
from django.conf import settings
from collections import defaultdict

class SystemMetricsService:
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Collect system health metrics"""
        # Get CPU metrics
        cpu_metrics = {
            'cpu_usage': psutil.cpu_percent(interval=1),
            'cpu_count': psutil.cpu_count(),
            'load_avg': psutil.getloadavg(),  # 1min, 5min, 15min averages
        }
        
        # Get memory metrics
        memory = psutil.virtual_memory()
        memory_metrics = {
            'memory_usage': memory.percent,
            'memory_available': memory.available,
            'memory_total': memory.total,
        }
        
        # Get disk metrics
        disk = psutil.disk_usage('/')
        disk_metrics = {
            'disk_usage': disk.percent,
            'disk_free': disk.free,
            'disk_total': disk.total,
        }
        
        # Get network metrics
        network = psutil.net_io_counters()
        network_metrics = {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv,
        }
        
        # Get process metrics
        process = psutil.Process(os.getpid())
        process_metrics = {
            'process_cpu': process.cpu_percent(),
            'process_memory': process.memory_percent(),
            'process_threads': process.num_threads(),
            'process_connections': len(process.connections()),
        }
        
        return {
            **cpu_metrics,
            **memory_metrics,
            **disk_metrics,
            **network_metrics,
            **process_metrics,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_database_metrics() -> Dict[str, Any]:
        """Collect database performance metrics"""
        metrics = {}
        
        # Get database engine type
        db_engine = connection.vendor
        
        if db_engine == 'postgresql':
            with connection.cursor() as cursor:
                # Connection metrics
                cursor.execute("SELECT count(*) FROM pg_stat_activity")
                metrics['active_connections'] = cursor.fetchone()[0]
                
                # Database size
                cursor.execute("SELECT pg_database_size(current_database())")
                metrics['database_size_bytes'] = cursor.fetchone()[0]
                
                # Table metrics
                cursor.execute("""
                    SELECT relname, n_live_tup, n_dead_tup
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                """)
                metrics['table_stats'] = [
                    {'table': row[0], 'live_rows': row[1], 'dead_rows': row[2]}
                    for row in cursor.fetchall()
                ]
                
                # Index usage
                cursor.execute("""
                    SELECT schemaname, relname, indexrelname, idx_scan
                    FROM pg_stat_user_indexes
                    ORDER BY idx_scan DESC
                """)
                metrics['index_usage'] = [
                    {
                        'table': row[1],
                        'index': row[2],
                        'scans': row[3]
                    }
                    for row in cursor.fetchall()
                ]
        
        elif db_engine == 'sqlite':
            db_path = connection.settings_dict['NAME']
            if os.path.exists(db_path):
                metrics['database_size_bytes'] = os.path.getsize(db_path)
                
                # Get table information
                with connection.cursor() as cursor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    
                    metrics['table_stats'] = []
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                        row_count = cursor.fetchone()[0]
                        metrics['table_stats'].append({
                            'table': table[0],
                            'rows': row_count
                        })
            else:
                metrics['database_size_bytes'] = 0
            
            metrics['active_connections'] = 1
        
        return metrics
    
    @staticmethod
    def get_response_metrics() -> Dict[str, Any]:
        """Get response time metrics from cache"""
        response_times = cache.get('response_times', [])
        endpoint_times = cache.get('endpoint_times', defaultdict(list))
        
        metrics = {
            'avg_response_time': 0,
            'max_response_time': 0,
            'min_response_time': 0,
            'endpoint_metrics': {}
        }
        
        if response_times:
            metrics.update({
                'avg_response_time': sum(response_times) / len(response_times),
                'max_response_time': max(response_times),
                'min_response_time': min(response_times),
                'total_requests': len(response_times)
            })
        
        # Calculate per-endpoint metrics
        for endpoint, times in endpoint_times.items():
            if times:
                metrics['endpoint_metrics'][endpoint] = {
                    'avg_time': sum(times) / len(times),
                    'max_time': max(times),
                    'min_time': min(times),
                    'requests': len(times)
                }
        
        return metrics
    
    @staticmethod
    def get_error_metrics() -> Dict[str, Any]:
        """Get error rate metrics from cache"""
        error_count = cache.get('error_count', 0)
        request_count = cache.get('request_count', 0)
        error_types = cache.get('error_types', defaultdict(int))
        
        return {
            'error_count': error_count,
            'request_count': request_count,
            'error_rate': (error_count / request_count * 100) if request_count > 0 else 0,
            'error_types': dict(error_types)  # Convert defaultdict to regular dict
        }
    
    @staticmethod
    def get_cache_metrics() -> Dict[str, Any]:
        """Get cache performance metrics"""
        hits = cache.get('cache_hits', 0)
        misses = cache.get('cache_misses', 0)
        total = hits + misses
        
        return {
            'cache_hits': hits,
            'cache_misses': misses,
            'hit_rate': (hits / total * 100) if total > 0 else 0,
            'total_operations': total
        }

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
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from ..services.monitoring import PerformanceMonitor
import asyncio
import json

class MonitoringConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection"""
        # Check if user is admin
        if not await self.is_admin():
            await self.close()
            return
        
        await self.accept()
        await self.channel_layer.group_add("monitoring", self.channel_name)
        
        # Start sending metrics
        self.send_metrics_task = asyncio.create_task(self.send_metrics_periodically())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard("monitoring", self.channel_name)
        if hasattr(self, 'send_metrics_task'):
            self.send_metrics_task.cancel()

    async def receive_json(self, content):
        """Handle incoming WebSocket messages"""
        command = content.get('command')
        if command == 'get_metrics':
            await self.send_metrics()

    async def monitoring_update(self, event):
        """Handle monitoring updates from channel layer"""
        await self.send_json(event['data'])

    @database_sync_to_async
    def is_admin(self):
        """Check if user has admin privileges"""
        return self.scope['user'].is_authenticated and self.scope['user'].role == 'ADMIN'

    @database_sync_to_async
    def get_metrics(self):
        """Get metrics from monitoring service"""
        metrics = PerformanceMonitor.monitor_resource_usage()
        historical = PerformanceMonitor.get_historical_metrics(days=1)
        alerts = PerformanceMonitor.get_alerts()
        return {
            'current': metrics,
            'historical': historical,
            'alerts': alerts
        }

    async def send_metrics(self):
        """Send metrics to client"""
        metrics = await self.get_metrics()
        await self.send_json({
            'type': 'metrics_update',
            'data': metrics
        })

    async def send_metrics_periodically(self):
        """Send metrics every 5 seconds"""
        while True:
            try:
                await self.send_metrics()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error sending metrics: {e}")
                await asyncio.sleep(5) 
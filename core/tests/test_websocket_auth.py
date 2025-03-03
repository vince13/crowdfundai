from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from django.urls import re_path
from core.consumers.notifications import NotificationConsumer
from channels.auth import AuthMiddlewareStack

class WebSocketAuthTest(TransactionTestCase):
    async def test_websocket_auth(self):
        # Create a test user
        User = get_user_model()
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create application with auth middleware
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
            ])
        )
        
        # Connect to websocket
        communicator = WebsocketCommunicator(
            application=application,
            path="/ws/notifications/"
        )
        
        try:
            # Attempt connection
            connected, _ = await communicator.connect()
            
            # Verify connection was rejected (since we're not authenticated)
            self.assertFalse(connected, "WebSocket connection should be rejected when not authenticated")
        finally:
            # Clean up
            await communicator.disconnect()
            await database_sync_to_async(user.delete)() 
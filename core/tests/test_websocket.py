from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, Client
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from django.urls import re_path
from core.consumers.notifications import NotificationConsumer
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack

class WebSocketAuthTest(TransactionTestCase):
    async def test_websocket_auth_unauthenticated(self):
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

    async def test_websocket_auth_authenticated(self):
        # Create a test user
        User = get_user_model()
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a regular HTTP client and log in
        client = Client()
        logged_in = await database_sync_to_async(client.login)(
            username='testuser',
            password='testpass123'
        )
        self.assertTrue(logged_in)
        
        # Get the session and session key
        session = client.session
        session_key = session.session_key
        
        # Create application with auth middleware
        application = AuthMiddlewareStack(
            SessionMiddlewareStack(
                URLRouter([
                    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
                ])
            )
        )
        
        # Connect to websocket with session ID
        communicator = WebsocketCommunicator(
            application=application,
            path="/ws/notifications/",
            headers=[(b"cookie", f"sessionid={session_key}".encode())],
        )
        
        try:
            # Attempt connection
            connected, _ = await communicator.connect()
            
            # Verify connection was successful
            self.assertTrue(connected, "WebSocket connection should be accepted when authenticated")
        finally:
            # Clean up
            await communicator.disconnect()
            await database_sync_to_async(user.delete)() 
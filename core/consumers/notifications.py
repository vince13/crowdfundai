import json
import logging
import traceback
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import ChannelFull
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from ..models import Notification
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Log connection attempt details
            logger.info("=== WebSocket Connection Attempt ===")
            logger.info(f"Headers: {dict(self.scope.get('headers', []))}")
            logger.info(f"Cookies: {self.scope.get('cookies', {})}")
            logger.info(f"Session: {self.scope.get('session', {})}")
            
            # Accept the connection before authentication
            await self.accept()
            logger.info("WebSocket connection initially accepted")
            
            # Get authenticated user
            self.user = await self.get_authenticated_user()
            if not self.user:
                logger.error("Authentication failed - closing connection")
                await self.close(code=4003)
                return
                
            logger.info(f"Authenticated user: {self.user.email}")
            
            # Set up notification group
            self.room_group_name = f"user_{self.user.id}_notifications"
            logger.info(f"Setting up room group: {self.room_group_name}")
            
            try:
                # Join room group
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
                logger.info(f"Added to channel group: {self.room_group_name}")
                
                # Send initial connection success message
                await self.send_json({
                    "type": "connection_established",
                    "message": "Connected successfully"
                })
                logger.info("Sent connection success message")
                
            except Exception as e:
                logger.error(f"Channel layer error: {str(e)}")
                logger.error(f"Channel layer traceback: {traceback.format_exc()}")
                await self.close(code=4500)
                return
                
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            logger.error(f"Connection traceback: {traceback.format_exc()}")
            if hasattr(self, 'close'):
                await self.close(code=4500)

    @database_sync_to_async
    def get_authenticated_user(self):
        """Get the authenticated user from the scope."""
        try:
            if "user" not in self.scope:
                logger.error("No user in scope")
                logger.error(f"Scope contents: {self.scope}")
                return None
            
            user = self.scope["user"]
            
            if isinstance(user, AnonymousUser):
                logger.error("User is AnonymousUser")
                logger.error(f"Headers: {dict(self.scope.get('headers', []))}")
                logger.error(f"Cookies: {self.scope.get('cookies', {})}")
                return None
            
            if not user.is_authenticated:
                logger.error("User is not authenticated")
                return None
                
            logger.info(f"Authenticated user found: {user.email}")
            return user
            
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            logger.info(f"WebSocket disconnected with code: {close_code}")
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
            logger.error(traceback.format_exc())
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(user=self.user, is_read=False).count()
    
    async def receive_json(self, content):
        try:
            message_type = content.get('type')
            
            if message_type == 'authenticate':
                # Handle authentication message
                logger.info("Received authentication message")
                if not hasattr(self, 'user') or not self.user:
                    logger.warning("Authentication failed - no user found")
                    await self.send_json({
                        'type': 'error',
                        'message': 'Authentication failed'
                    })
                    await self.close(code=4003)
                else:
                    logger.info(f"Authentication successful for user: {self.user.email}")
                    await self.send_json({
                        'type': 'authentication_success'
                    })
            
            elif message_type == 'mark_read':
                notification_id = content.get('notification_id')
                await self.mark_notification_read(notification_id)
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def notification(self, event):
        # Send notification to WebSocket
        await self.send_json(event['data'])
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False 

    async def notification_message(self, event):
        """Handle notification messages"""
        await self.send_json(event["data"]) 
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import ChatRoom, Call


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'call_{self.room_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        # Handle call ended messages specially
        if message_type == 'call_ended':
            # End any active calls in the database
            await self.end_active_calls()
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_message',
                'message': text_data_json
            }
        )
    
    @database_sync_to_async
    def end_active_calls(self):
        """End any active calls in this room"""
        try:
            from .models import Call
            from django.utils import timezone
            
            # Find active calls in this room
            active_calls = Call.objects.filter(
                chat_room_id=self.room_id,
                status__in=['initiated', 'ringing', 'connected']
            )
            
            # End all active calls
            for call in active_calls:
                call.status = 'ended'
                call.ended_at = timezone.now()
                if call.connected_at and not call.duration:
                    call.duration = call.ended_at - call.connected_at
                call.save()
                
        except Exception as e:
            print(f"Error ending active calls: {e}")
    
    async def call_message(self, event):
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps(message))
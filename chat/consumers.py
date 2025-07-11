import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import ChatRoom, Call, CallParticipant

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
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
        
        if message_type == 'chat_message':
            message = text_data_json['message']
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': self.scope['user'].username,
                    'timestamp': timezone.now().isoformat()
                }
            )

    async def chat_message(self, event):
        message = event['message']
        user = event['user']
        timestamp = event['timestamp']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message,
            'user': user,
            'timestamp': timestamp
        }))


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'call_{self.room_id}'
        self.user = self.scope['user']
        
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
        
        # Handle user leaving call
        await self.handle_user_left_call()

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'call_initiate':
                await self.handle_call_initiate(text_data_json)
            elif message_type == 'call_answer':
                await self.handle_call_answer(text_data_json)
            elif message_type == 'call_reject':
                await self.handle_call_reject(text_data_json)
            elif message_type == 'call_end':
                await self.handle_call_end(text_data_json)
            elif message_type == 'webrtc_offer':
                await self.handle_webrtc_offer(text_data_json)
            elif message_type == 'webrtc_answer':
                await self.handle_webrtc_answer(text_data_json)
            elif message_type == 'webrtc_ice_candidate':
                await self.handle_webrtc_ice_candidate(text_data_json)
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_call_initiate(self, data):
        call_type = data.get('call_type', 'audio')
        
        # Create call in database
        call = await self.create_call(self.room_id, self.user.id, call_type)
        
        # Notify all participants in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_initiated',
                'call_id': call.id,
                'caller': self.user.username,
                'call_type': call_type,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_call_answer(self, data):
        call_id = data.get('call_id')
        
        # Update call status
        await self.update_call_status(call_id, 'connected')
        
        # Notify participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_answered',
                'call_id': call_id,
                'user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_call_reject(self, data):
        call_id = data.get('call_id')
        
        # Update call status
        await self.update_call_status(call_id, 'rejected')
        
        # Notify participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_rejected',
                'call_id': call_id,
                'user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_call_end(self, data):
        call_id = data.get('call_id')
        
        # Update call status
        await self.update_call_status(call_id, 'ended')
        
        # Notify participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_ended',
                'call_id': call_id,
                'user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_webrtc_offer(self, data):
        # Forward WebRTC offer to other participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_offer',
                'offer': data['offer'],
                'from_user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_webrtc_answer(self, data):
        # Forward WebRTC answer to other participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_answer',
                'answer': data['answer'],
                'from_user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_webrtc_ice_candidate(self, data):
        # Forward ICE candidate to other participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_ice_candidate',
                'candidate': data['candidate'],
                'from_user': self.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_user_left_call(self):
        # Handle user leaving call gracefully
        pass

    # Event handlers for group messages
    async def call_initiated(self, event):
        await self.send(text_data=json.dumps(event))

    async def call_answered(self, event):
        await self.send(text_data=json.dumps(event))

    async def call_rejected(self, event):
        await self.send(text_data=json.dumps(event))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps(event))

    async def webrtc_offer(self, event):
        # Don't send offer back to sender
        if event['from_user'] != self.user.username:
            await self.send(text_data=json.dumps(event))

    async def webrtc_answer(self, event):
        # Don't send answer back to sender
        if event['from_user'] != self.user.username:
            await self.send(text_data=json.dumps(event))

    async def webrtc_ice_candidate(self, event):
        # Don't send candidate back to sender
        if event['from_user'] != self.user.username:
            await self.send(text_data=json.dumps(event))

    # Database operations
    @database_sync_to_async
    def create_call(self, room_id, caller_id, call_type):
        from .models import ChatRoom, Call, CallParticipant
        
        chat_room = ChatRoom.objects.get(id=room_id)
        caller = User.objects.get(id=caller_id)
        
        call = Call.objects.create(
            chat_room=chat_room,
            caller=caller,
            call_type=call_type,
            status='initiated'
        )
        
        # Add all chat room participants to the call
        for participant in chat_room.participants.all():
            CallParticipant.objects.create(
                call=call,
                user=participant,
                status='invited'
            )
        
        return call

    @database_sync_to_async
    def update_call_status(self, call_id, status):
        try:
            call = Call.objects.get(id=call_id)
            call.status = status
            if status == 'connected':
                call.connected_at = timezone.now()
            elif status == 'ended':
                call.ended_at = timezone.now()
                if call.connected_at:
                    call.duration = call.ended_at - call.connected_at
            call.save()
            return call
        except Call.DoesNotExist:
            return None
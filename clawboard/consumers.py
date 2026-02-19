"""
Clawboard WebSocket Consumer
Empfängt Verbindungen von lokalen OpenClaw/Clawdbot Gateways
"""
import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class GatewayConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer für Gateway-Verbindungen.
    
    Protokoll:
    1. Client verbindet sich
    2. Client sendet auth-Message mit Token
    3. Server validiert Token und bestätigt
    4. Heartbeats alle 30 Sekunden
    5. Server kann Commands senden, Client antwortet
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection = None
        self.authenticated = False
        self.connection_id = None
    
    async def connect(self):
        """Neue WebSocket-Verbindung"""
        await self.accept()
        logger.info(f"Gateway connection opened from {self.scope.get('client', ['unknown'])[0]}")
    
    async def disconnect(self, close_code):
        """Verbindung geschlossen"""
        if self.connection:
            await self.set_connection_offline()
        logger.info(f"Gateway disconnected: {self.connection_id}, code={close_code}")
    
    async def receive(self, text_data):
        """Nachricht vom Gateway empfangen"""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')
            
            if msg_type == 'auth':
                await self.handle_auth(data)
            elif not self.authenticated:
                await self.send_error("Not authenticated")
                await self.close()
            elif msg_type == 'heartbeat':
                await self.handle_heartbeat(data)
            elif msg_type == 'command_result':
                await self.handle_command_result(data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            await self.send_error(str(e))
    
    async def handle_auth(self, data):
        """Authentifizierung verarbeiten"""
        token = data.get('token')
        gateway_info = data.get('gateway_info', {})
        
        if not token:
            await self.send_json({
                'type': 'auth_result',
                'success': False,
                'error': 'Token required'
            })
            await self.close()
            return
        
        # Token validieren und Connection finden
        connection = await self.validate_token(token)
        
        if not connection:
            await self.send_json({
                'type': 'auth_result',
                'success': False,
                'error': 'Invalid token'
            })
            await self.close()
            return
        
        # Verbindung speichern
        self.connection = connection
        self.connection_id = str(connection.pk)
        self.authenticated = True
        
        # Connection als online markieren
        await self.set_connection_online(gateway_info)
        
        # Channel-Group beitreten für diesen User
        await self.channel_layer.group_add(
            f"gateway_{connection.pk}",
            self.channel_name
        )
        
        await self.send_json({
            'type': 'auth_result',
            'success': True,
            'connection_id': self.connection_id
        })
        
        logger.info(f"Gateway authenticated: {connection.name} (ID: {connection.pk})")
    
    async def handle_heartbeat(self, data):
        """Heartbeat verarbeiten"""
        system_info = data.get('system', {})
        
        await self.update_connection_status(system_info)
        
        await self.send_json({
            'type': 'heartbeat_ack',
            'timestamp': datetime.now().isoformat()
        })
    
    async def handle_command_result(self, data):
        """Command-Ergebnis vom Gateway"""
        command_id = data.get('id')
        # Hier könnte man das Ergebnis an wartende Requests weiterleiten
        # Für jetzt loggen wir es nur
        logger.info(f"Command result received: {command_id}")
    
    async def send_command(self, event):
        """Command an Gateway senden (von Channel Layer)"""
        await self.send_json({
            'type': 'command',
            'id': event['command_id'],
            'action': event['action'],
            'params': event.get('params', {})
        })
    
    async def send_json(self, data):
        """JSON senden"""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message):
        """Fehler senden"""
        await self.send_json({
            'type': 'error',
            'message': message
        })
    
    @database_sync_to_async
    def validate_token(self, token):
        """Token validieren und Connection zurückgeben"""
        from .models import ClawdbotConnection
        try:
            return ClawdbotConnection.objects.get(
                gateway_token=token,
                is_active=True
            )
        except ClawdbotConnection.DoesNotExist:
            return None
    
    @database_sync_to_async
    def set_connection_online(self, gateway_info):
        """Connection als online markieren"""
        from .models import ClawdbotConnection
        ClawdbotConnection.objects.filter(pk=self.connection.pk).update(
            status='online',
            last_seen=timezone.now(),
            gateway_version=gateway_info.get('version', ''),
            hostname=gateway_info.get('hostname', '')
        )
    
    @database_sync_to_async
    def set_connection_offline(self):
        """Connection als offline markieren"""
        from .models import ClawdbotConnection
        ClawdbotConnection.objects.filter(pk=self.connection.pk).update(
            status='offline',
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def update_connection_status(self, system_info):
        """System-Status aktualisieren"""
        from .models import ClawdbotConnection
        ClawdbotConnection.objects.filter(pk=self.connection.pk).update(
            last_seen=timezone.now(),
            cpu_percent=system_info.get('cpu_percent'),
            ram_used_mb=system_info.get('ram_used_mb'),
            ram_total_mb=system_info.get('ram_total_mb'),
            disk_used_gb=system_info.get('disk_used_gb'),
            disk_total_gb=system_info.get('disk_total_gb')
        )

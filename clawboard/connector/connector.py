#!/usr/bin/env python3
"""
Clawboard Connector

Verbindet einen lokalen OpenClaw/Clawdbot Gateway mit Clawboard auf workloom.de.
Der Connector baut eine ausgehende WebSocket-Verbindung auf (funktioniert durch NAT/Firewall).

Verwendung:
    python3 connector.py                    # Mit Konfig aus ~/.clawdbot/clawboard-connector.json
    python3 connector.py --config /path/to/config.json

Konfiguration (~/.clawdbot/clawboard-connector.json):
{
    "workloom_url": "wss://www.workloom.de/ws/clawboard/gateway/",
    "connection_token": "dein-token-von-workloom",
    "gateway_url": "ws://localhost:18789",
    "gateway_token": "dein-lokaler-gateway-token",
    "heartbeat_interval": 30,
    "reconnect_delay": 10
}
"""

import os
import sys
import json
import time
import asyncio
import signal
import logging
import argparse
import platform
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import websockets
except ImportError:
    print("ERROR: websockets nicht installiert!")
    print("Installiere mit: pip install websockets")
    sys.exit(1)

try:
    import psutil
except ImportError:
    psutil = None
    print("WARNING: psutil nicht installiert - System-Metriken werden nicht gesendet")
    print("Installiere mit: pip install psutil")


# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('clawboard-connector')


class ClawboardConnector:
    """
    Connector zwischen lokalem Gateway und Clawboard (workloom.de)
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.workloom_url = config.get('workloom_url', 'wss://www.workloom.de/ws/clawboard/gateway/')
        self.connection_token = config.get('connection_token')
        self.gateway_url = config.get('gateway_url', 'ws://localhost:18789')
        self.gateway_token = config.get('gateway_token')
        self.heartbeat_interval = config.get('heartbeat_interval', 30)
        self.reconnect_delay = config.get('reconnect_delay', 10)
        
        self.ws = None
        self.running = True
        self.authenticated = False
        
        if not self.connection_token:
            raise ValueError("connection_token ist erforderlich!")
    
    def get_system_info(self) -> dict:
        """System-Metriken sammeln"""
        info = {}
        
        if psutil:
            try:
                info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                info['ram_used_mb'] = mem.used / (1024 * 1024)
                info['ram_total_mb'] = mem.total / (1024 * 1024)
                disk = psutil.disk_usage('/')
                info['disk_used_gb'] = disk.used / (1024 * 1024 * 1024)
                info['disk_total_gb'] = disk.total / (1024 * 1024 * 1024)
            except Exception as e:
                logger.warning(f"Fehler beim Sammeln von System-Metriken: {e}")
        
        return info
    
    def get_gateway_info(self) -> dict:
        """Gateway-Informationen sammeln"""
        info = {
            'hostname': platform.node(),
            'platform': platform.system(),
        }
        
        # OpenClaw/Clawdbot Version ermitteln
        try:
            result = subprocess.run(
                ['openclaw', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['version'] = result.stdout.strip()
        except:
            try:
                result = subprocess.run(
                    ['clawdbot', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    info['version'] = result.stdout.strip()
            except:
                info['version'] = 'unknown'
        
        return info
    
    async def send_json(self, data: dict):
        """JSON an Workloom senden"""
        if self.ws:
            await self.ws.send(json.dumps(data))
    
    async def authenticate(self):
        """Bei Workloom authentifizieren"""
        logger.info("Authentifiziere bei Workloom...")
        
        await self.send_json({
            'type': 'auth',
            'token': self.connection_token,
            'gateway_info': self.get_gateway_info()
        })
        
        # Auf Antwort warten
        response = await self.ws.recv()
        data = json.loads(response)
        
        if data.get('type') == 'auth_result':
            if data.get('success'):
                self.authenticated = True
                logger.info(f"✓ Authentifizierung erfolgreich (ID: {data.get('connection_id')})")
                return True
            else:
                logger.error(f"✗ Authentifizierung fehlgeschlagen: {data.get('error')}")
                return False
        
        logger.error(f"Unerwartete Antwort: {data}")
        return False
    
    async def heartbeat_loop(self):
        """Heartbeat-Loop"""
        while self.running and self.authenticated:
            try:
                await self.send_json({
                    'type': 'heartbeat',
                    'timestamp': datetime.now().isoformat(),
                    'system': self.get_system_info()
                })
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat-Fehler: {e}")
                break
    
    async def handle_command(self, data: dict):
        """Command von Workloom verarbeiten"""
        command_id = data.get('id')
        action = data.get('action')
        params = data.get('params', {})
        
        logger.info(f"Command empfangen: {action} (ID: {command_id})")
        
        result = {'success': False, 'error': 'Unknown action'}
        
        try:
            if action == 'read_file':
                result = await self.cmd_read_file(params)
            elif action == 'write_file':
                result = await self.cmd_write_file(params)
            elif action == 'list_files':
                result = await self.cmd_list_files(params)
            elif action == 'get_status':
                result = await self.cmd_get_status()
            else:
                result = {'success': False, 'error': f'Unknown action: {action}'}
        except Exception as e:
            result = {'success': False, 'error': str(e)}
        
        # Ergebnis senden
        await self.send_json({
            'type': 'command_result',
            'id': command_id,
            **result
        })
    
    async def cmd_read_file(self, params: dict) -> dict:
        """Datei lesen"""
        path = params.get('path')
        if not path:
            return {'success': False, 'error': 'path required'}
        
        # Relative Pfade relativ zum Workspace
        workspace = os.environ.get('CLAWDBOT_WORKSPACE', os.path.expanduser('~/clawd'))
        full_path = os.path.join(workspace, path) if not os.path.isabs(path) else path
        
        # Sicherheitscheck: Nur Dateien im Workspace erlauben
        if not os.path.abspath(full_path).startswith(os.path.abspath(workspace)):
            return {'success': False, 'error': 'Access denied'}
        
        if not os.path.exists(full_path):
            return {'success': False, 'error': 'File not found'}
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            stat = os.stat(full_path)
            return {
                'success': True,
                'data': {
                    'content': content,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def cmd_write_file(self, params: dict) -> dict:
        """Datei schreiben"""
        path = params.get('path')
        content = params.get('content')
        
        if not path or content is None:
            return {'success': False, 'error': 'path and content required'}
        
        workspace = os.environ.get('CLAWDBOT_WORKSPACE', os.path.expanduser('~/clawd'))
        full_path = os.path.join(workspace, path) if not os.path.isabs(path) else path
        
        if not os.path.abspath(full_path).startswith(os.path.abspath(workspace)):
            return {'success': False, 'error': 'Access denied'}
        
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def cmd_list_files(self, params: dict) -> dict:
        """Dateien auflisten"""
        directory = params.get('directory', '')
        
        workspace = os.environ.get('CLAWDBOT_WORKSPACE', os.path.expanduser('~/clawd'))
        full_path = os.path.join(workspace, directory) if directory else workspace
        
        if not os.path.abspath(full_path).startswith(os.path.abspath(workspace)):
            return {'success': False, 'error': 'Access denied'}
        
        if not os.path.isdir(full_path):
            return {'success': False, 'error': 'Not a directory'}
        
        try:
            files = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                stat = os.stat(item_path)
                files.append({
                    'name': item,
                    'is_dir': os.path.isdir(item_path),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return {'success': True, 'data': {'files': files}}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def cmd_get_status(self) -> dict:
        """System-Status abrufen"""
        return {
            'success': True,
            'data': {
                'system': self.get_system_info(),
                'gateway': self.get_gateway_info()
            }
        }
    
    async def message_loop(self):
        """Nachrichten-Loop"""
        while self.running and self.authenticated:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                
                msg_type = data.get('type')
                
                if msg_type == 'heartbeat_ack':
                    pass  # Ignorieren
                elif msg_type == 'command':
                    await self.handle_command(data)
                else:
                    logger.warning(f"Unbekannter Nachrichtentyp: {msg_type}")
            
            except websockets.ConnectionClosed:
                logger.warning("Verbindung geschlossen")
                break
            except Exception as e:
                logger.error(f"Fehler beim Empfangen: {e}")
                break
    
    async def run(self):
        """Hauptloop mit Reconnect"""
        while self.running:
            try:
                logger.info(f"Verbinde zu {self.workloom_url}...")
                
                async with websockets.connect(
                    self.workloom_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as ws:
                    self.ws = ws
                    self.authenticated = False
                    
                    # Authentifizieren
                    if not await self.authenticate():
                        logger.error("Authentifizierung fehlgeschlagen, warte vor Retry...")
                        await asyncio.sleep(self.reconnect_delay * 3)
                        continue
                    
                    # Heartbeat und Message Loops starten
                    heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                    message_task = asyncio.create_task(self.message_loop())
                    
                    # Warten bis einer fertig ist
                    done, pending = await asyncio.wait(
                        [heartbeat_task, message_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Aufräumen
                    for task in pending:
                        task.cancel()
                    
                    self.authenticated = False
            
            except websockets.ConnectionClosed as e:
                logger.warning(f"Verbindung geschlossen: {e}")
            except ConnectionRefusedError:
                logger.error("Verbindung abgelehnt - ist Workloom erreichbar?")
            except Exception as e:
                logger.error(f"Verbindungsfehler: {e}")
            
            if self.running:
                logger.info(f"Reconnect in {self.reconnect_delay} Sekunden...")
                await asyncio.sleep(self.reconnect_delay)
    
    def stop(self):
        """Connector stoppen"""
        logger.info("Stoppe Connector...")
        self.running = False


def load_config(config_path: str = None) -> dict:
    """Konfiguration laden"""
    if config_path is None:
        config_path = os.path.expanduser('~/.clawdbot/clawboard-connector.json')
    
    if not os.path.exists(config_path):
        # Standardkonfiguration erstellen
        default_config = {
            'workloom_url': 'wss://www.workloom.de/ws/clawboard/gateway/',
            'connection_token': 'DEIN-TOKEN-HIER',
            'gateway_url': 'ws://localhost:18789',
            'gateway_token': '',
            'heartbeat_interval': 30,
            'reconnect_delay': 10
        }
        
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"Konfigurationsdatei erstellt: {config_path}")
        print("Bitte bearbeite die Datei und trage deinen Connection Token ein!")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='Clawboard Connector')
    parser.add_argument('--config', '-c', help='Pfad zur Konfigurationsdatei')
    parser.add_argument('--debug', '-d', action='store_true', help='Debug-Modus')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = load_config(args.config)
    
    if config.get('connection_token') == 'DEIN-TOKEN-HIER':
        print("ERROR: Bitte trage deinen Connection Token in die Konfiguration ein!")
        print(f"Datei: {args.config or '~/.clawdbot/clawboard-connector.json'}")
        sys.exit(1)
    
    connector = ClawboardConnector(config)
    
    # Signal-Handler
    def signal_handler(sig, frame):
        connector.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Starten
    logger.info("Clawboard Connector gestartet")
    asyncio.run(connector.run())
    logger.info("Clawboard Connector beendet")


if __name__ == '__main__':
    main()

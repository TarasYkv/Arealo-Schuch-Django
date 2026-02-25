#!/usr/bin/env python3
"""
Clawboard Connector

Verbindet einen lokalen OpenClaw/Clawdbot Gateway mit Clawboard auf workloom.de.

Modi:
    --mode http  (Standard) Sendet Daten per HTTP POST - funktioniert ueberall
    --mode ws    WebSocket-Verbindung (benoetigt ASGI-Server)

Verwendung:
    python3 connector.py                    # HTTP-Modus (Standard)
    python3 connector.py --mode ws          # WebSocket-Modus
    python3 connector.py --config /path/to/config.json

Konfiguration (~/.clawdbot/clawboard-connector.json):
{
    "push_url": "https://www.workloom.de/clawboard/api/push/",
    "workloom_url": "wss://www.workloom.de/ws/clawboard/gateway/",
    "connection_token": "dein-token-von-workloom",
    "gateway_url": "ws://localhost:18789",
    "gateway_token": "dein-lokaler-gateway-token",
    "openclaw_token": "",
    "heartbeat_interval": 30,
    "reconnect_delay": 10,
    "workspace": "~/clawd"
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
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None
    print("WARNING: psutil nicht installiert - System-Metriken werden nicht gesendet")
    print("Installiere mit: pip install psutil")

# WebSocket ist optional (nur fuer --mode ws)
websockets = None
try:
    import websockets as _ws
    websockets = _ws
except ImportError:
    pass


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
    Unterstuetzt HTTP-Push und WebSocket Modi.
    """

    def __init__(self, config: dict, mode: str = 'http'):
        self.config = config
        self.mode = mode
        self.push_url = config.get('push_url', 'https://www.workloom.de/clawboard/api/push/')
        self.workloom_url = config.get('workloom_url', 'wss://www.workloom.de/ws/clawboard/gateway/')
        self.connection_token = config.get('connection_token')
        self.gateway_url = config.get('gateway_url', 'ws://localhost:18789')
        self.gateway_token = config.get('gateway_token')
        self.openclaw_token = config.get('openclaw_token', '') or self._detect_openclaw_token()
        self.heartbeat_interval = config.get('heartbeat_interval', 30)
        self.reconnect_delay = config.get('reconnect_delay', 10)
        self.workspace = os.path.expanduser(config.get('workspace', '~/clawd'))

        self.ws = None
        self.running = True
        self.authenticated = False

        # Gateway Chat Support
        self.pending_chat_responses = []
        self.cached_gateway_models = []
        self.last_model_fetch = 0
        self.model_fetch_interval = 300  # Alle 5 Minuten
        self.current_push_interval = self.heartbeat_interval

        if not self.connection_token:
            raise ValueError("connection_token ist erforderlich!")

        if self.openclaw_token:
            logger.info("OpenClaw Token konfiguriert")
        else:
            logger.info("Kein OpenClaw Token - Gateway-Requests ohne Auth")

    def _detect_openclaw_token(self) -> str:
        """Versucht den OpenClaw Gateway Token automatisch zu finden."""
        # 1. Umgebungsvariable
        env_token = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '')
        if env_token:
            logger.info("OpenClaw Token aus OPENCLAW_GATEWAY_TOKEN geladen")
            return env_token

        # 2. OpenClaw Config-Datei (~/.openclaw/openclaw.json)
        config_paths = [
            os.path.expanduser('~/.openclaw/openclaw.json'),
            os.path.expanduser('~/.clawdbot/config.json'),
        ]
        for cfg_path in config_paths:
            try:
                if os.path.exists(cfg_path):
                    with open(cfg_path, 'r') as f:
                        data = json.load(f)
                    # gateway.auth.token
                    token = (data.get('gateway', {}).get('auth', {}).get('token', '')
                             or data.get('gatewayToken', '')
                             or data.get('gateway_token', ''))
                    if token and not token.startswith('$'):
                        logger.info(f"OpenClaw Token aus {cfg_path} geladen")
                        return token
            except Exception:
                pass

        # 3. openclaw CLI
        try:
            result = subprocess.run(
                ['openclaw', 'config', 'get', 'gateway.auth.token'],
                capture_output=True, text=True, timeout=5
            )
            token = result.stdout.strip()
            if token and result.returncode == 0 and token != 'null' and token != '""':
                logger.info("OpenClaw Token via CLI geladen")
                return token
        except Exception:
            pass

        return ''

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

    def collect_memory_files(self) -> list:
        """Memory-Dateien aus dem Workspace sammeln"""
        memory_dir = os.path.join(self.workspace, 'memory')
        files = []

        if not os.path.isdir(memory_dir):
            # Auch MEMORY.md im Root pruefen
            memory_md = os.path.join(self.workspace, 'MEMORY.md')
            if os.path.exists(memory_md):
                try:
                    with open(memory_md, 'r', encoding='utf-8') as f:
                        content = f.read()
                    files.append({
                        'path': 'MEMORY.md',
                        'filename': 'MEMORY.md',
                        'content': content,
                        'size': os.path.getsize(memory_md),
                    })
                except Exception:
                    pass
            return files

        for root, dirs, filenames in os.walk(memory_dir):
            for fname in filenames:
                if not fname.endswith('.md'):
                    continue
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.workspace)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    files.append({
                        'path': rel_path,
                        'filename': fname,
                        'content': content,
                        'size': os.path.getsize(full_path),
                    })
                except Exception as e:
                    logger.warning(f"Fehler beim Lesen von {rel_path}: {e}")

        return files

    def _detect_cmd(self, cmd, version_flag='--version') -> str:
        """Versucht ein Kommando auszufuehren und gibt die Version zurueck."""
        try:
            result = subprocess.run(
                [cmd, version_flag],
                capture_output=True, text=True, timeout=5
            )
            output = (result.stdout or result.stderr).strip()
            # Erste Zeile, maximal 100 Zeichen
            return output.split('\n')[0][:100]
        except Exception:
            return ''

    def collect_skills(self) -> list:
        """Erkennt installierte Programmiersprachen/Runtimes/Tools."""
        checks = [
            # Programmiersprachen
            ('Python', 'python3', '--version', 'language', 'bi-filetype-py'),
            ('Node.js', 'node', '--version', 'language', 'bi-filetype-js'),
            ('Go', 'go', 'version', 'language', 'bi-code-square'),
            ('Rust', 'rustc', '--version', 'language', 'bi-gear-fill'),
            ('Java', 'java', '--version', 'language', 'bi-filetype-java'),
            ('Ruby', 'ruby', '--version', 'language', 'bi-gem'),
            ('PHP', 'php', '--version', 'language', 'bi-filetype-php'),
            ('TypeScript', 'tsc', '--version', 'language', 'bi-filetype-tsx'),
            ('Perl', 'perl', '--version', 'language', 'bi-code'),
            ('Lua', 'lua', '-v', 'language', 'bi-code'),
            ('Swift', 'swift', '--version', 'language', 'bi-code-slash'),
            ('Kotlin', 'kotlin', '-version', 'language', 'bi-code-slash'),
            ('Scala', 'scala', '-version', 'language', 'bi-code-slash'),
            ('Dart', 'dart', '--version', 'language', 'bi-code-slash'),
            ('Elixir', 'elixir', '--version', 'language', 'bi-droplet'),
            ('Haskell', 'ghc', '--version', 'language', 'bi-code'),
            # Compiler & Build-Tools
            ('GCC', 'gcc', '--version', 'tool', 'bi-cpu'),
            ('Clang', 'clang', '--version', 'tool', 'bi-cpu'),
            ('CMake', 'cmake', '--version', 'tool', 'bi-tools'),
            ('Gradle', 'gradle', '--version', 'tool', 'bi-tools'),
            ('Maven', 'mvn', '--version', 'tool', 'bi-tools'),
            ('.NET', 'dotnet', '--version', 'tool', 'bi-microsoft'),
            # Container & Cloud
            ('Docker', 'docker', '--version', 'tool', 'bi-box-seam'),
            ('Docker Compose', 'docker-compose', '--version', 'tool', 'bi-boxes'),
            ('Podman', 'podman', '--version', 'tool', 'bi-box-seam'),
            ('kubectl', 'kubectl', 'version --client --short', 'tool', 'bi-cloud'),
            ('Terraform', 'terraform', '--version', 'tool', 'bi-cloud-arrow-up'),
            ('Ansible', 'ansible', '--version', 'tool', 'bi-gear'),
            # Paket-Manager
            ('pip', 'pip3', '--version', 'tool', 'bi-box-arrow-down'),
            ('npm', 'npm', '--version', 'tool', 'bi-box'),
            ('yarn', 'yarn', '--version', 'tool', 'bi-box'),
            ('pnpm', 'pnpm', '--version', 'tool', 'bi-box'),
            ('cargo', 'cargo', '--version', 'tool', 'bi-box'),
            ('Homebrew', 'brew', '--version', 'tool', 'bi-cup-straw'),
        ]
        skills = []
        for name, cmd, flag, category, icon in checks:
            ver = self._detect_cmd(cmd, flag)
            if ver:
                skills.append({
                    'name': name,
                    'category': category,
                    'version': ver,
                    'icon': icon,
                })
        return skills

    def collect_integrations(self) -> list:
        """Erkennt installierte Developer-Tools und Services."""
        checks = [
            ('Git', 'git', '--version', 'vcs', 'bi-git'),
            ('curl', 'curl', '--version', 'cli', 'bi-globe'),
            ('wget', 'wget', '--version', 'cli', 'bi-download'),
            ('Make', 'make', '--version', 'build', 'bi-tools'),
            ('nginx', 'nginx', '-v', 'server', 'bi-server'),
            ('Apache', 'apache2', '-v', 'server', 'bi-server'),
            ('PostgreSQL', 'psql', '--version', 'database', 'bi-database'),
            ('MySQL', 'mysql', '--version', 'database', 'bi-database'),
            ('Redis', 'redis-cli', '--version', 'database', 'bi-database'),
            ('MongoDB', 'mongod', '--version', 'database', 'bi-database'),
            ('SQLite', 'sqlite3', '--version', 'database', 'bi-database'),
            ('tmux', 'tmux', '-V', 'cli', 'bi-terminal'),
            ('screen', 'screen', '--version', 'cli', 'bi-terminal'),
            ('htop', 'htop', '--version', 'cli', 'bi-speedometer'),
            ('jq', 'jq', '--version', 'cli', 'bi-braces'),
            ('ffmpeg', 'ffmpeg', '-version', 'media', 'bi-film'),
            ('ImageMagick', 'convert', '--version', 'media', 'bi-image'),
            ('pandoc', 'pandoc', '--version', 'cli', 'bi-file-earmark-text'),
        ]
        integrations = []
        for name, cmd, flag, category, icon in checks:
            ver = self._detect_cmd(cmd, flag)
            if ver:
                integrations.append({
                    'name': name,
                    'category': category,
                    'version': ver,
                    'icon': icon,
                    'status': 'active',
                })

        # SSH-Key vorhanden?
        ssh_key = os.path.expanduser('~/.ssh/id_rsa')
        ssh_key_ed = os.path.expanduser('~/.ssh/id_ed25519')
        if os.path.exists(ssh_key) or os.path.exists(ssh_key_ed):
            integrations.append({
                'name': 'SSH Key',
                'category': 'ssh',
                'version': '',
                'icon': 'bi-key',
                'status': 'active',
            })

        return integrations

    def collect_projects(self) -> list:
        """Erkennt Projekte im Workspace (Git-Repos, package.json etc.)."""
        projects = []
        workspace = self.workspace
        if not os.path.isdir(workspace):
            return projects

        # Direkte Unterordner des Workspace durchsuchen
        try:
            for item in os.listdir(workspace):
                item_path = os.path.join(workspace, item)
                if not os.path.isdir(item_path) or item.startswith('.'):
                    continue

                project = {'name': item, 'path': item_path, 'type': 'unknown', 'icon': ''}

                # Git-Repo?
                if os.path.isdir(os.path.join(item_path, '.git')):
                    project['type'] = 'git'
                    project['icon'] = 'bi-git'

                # Sprache/Framework erkennen
                if os.path.exists(os.path.join(item_path, 'package.json')):
                    project['type'] = 'nodejs'
                    project['icon'] = 'bi-filetype-js'
                elif os.path.exists(os.path.join(item_path, 'requirements.txt')) or \
                     os.path.exists(os.path.join(item_path, 'setup.py')) or \
                     os.path.exists(os.path.join(item_path, 'pyproject.toml')):
                    project['type'] = 'python'
                    project['icon'] = 'bi-filetype-py'
                elif os.path.exists(os.path.join(item_path, 'Cargo.toml')):
                    project['type'] = 'rust'
                    project['icon'] = 'bi-gear-fill'
                elif os.path.exists(os.path.join(item_path, 'go.mod')):
                    project['type'] = 'go'
                    project['icon'] = 'bi-code-square'
                elif os.path.exists(os.path.join(item_path, 'pom.xml')) or \
                     os.path.exists(os.path.join(item_path, 'build.gradle')):
                    project['type'] = 'java'
                    project['icon'] = 'bi-filetype-java'
                elif os.path.exists(os.path.join(item_path, 'Gemfile')):
                    project['type'] = 'ruby'
                    project['icon'] = 'bi-gem'
                elif os.path.exists(os.path.join(item_path, 'Dockerfile')):
                    project['type'] = 'docker'
                    project['icon'] = 'bi-box-seam'

                projects.append(project)
        except Exception as e:
            logger.warning(f"Fehler beim Scannen des Workspace: {e}")

        return projects[:20]  # Max 20 Projekte

    def collect_conversations(self) -> list:
        """Sammelt Konversationen aus dem Workspace."""
        conversations = []

        # 1. Clawdbot-Konversationen aus ~/.clawdbot/conversations/
        conv_dirs = [
            os.path.expanduser('~/.clawdbot/conversations'),
            os.path.join(self.workspace, 'conversations'),
            os.path.join(self.workspace, '.conversations'),
        ]

        for conv_dir in conv_dirs:
            if not os.path.isdir(conv_dir):
                continue
            try:
                for fname in sorted(os.listdir(conv_dir), reverse=True)[:20]:
                    fpath = os.path.join(conv_dir, fname)
                    if not os.path.isfile(fpath):
                        continue

                    if fname.endswith('.json'):
                        try:
                            with open(fpath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            conversations.append({
                                'session_key': data.get('session_key', fname),
                                'title': data.get('title', fname.replace('.json', '')),
                                'summary': data.get('summary', ''),
                                'messages': data.get('messages', [])[:5],
                                'message_count': len(data.get('messages', [])),
                                'total_tokens': data.get('total_tokens', 0),
                                'total_cost': data.get('total_cost', 0),
                                'channel': data.get('channel', 'local'),
                                'started_at': data.get('started_at',
                                    datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()),
                            })
                        except Exception:
                            pass

                    elif fname.endswith('.jsonl'):
                        # Transcript-Format (Claude Code Style)
                        try:
                            msg_count = 0
                            first_line = None
                            with open(fpath, 'r', encoding='utf-8') as f:
                                for line in f:
                                    msg_count += 1
                                    if first_line is None:
                                        first_line = line.strip()
                            title = fname.replace('.jsonl', '')
                            if first_line:
                                try:
                                    first = json.loads(first_line)
                                    if first.get('content'):
                                        title = str(first['content'])[:80]
                                except Exception:
                                    pass
                            conversations.append({
                                'session_key': fname,
                                'title': title,
                                'summary': '',
                                'messages': [],
                                'message_count': msg_count,
                                'channel': 'local',
                                'started_at': datetime.fromtimestamp(
                                    os.path.getmtime(fpath)).isoformat(),
                            })
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"Konversationen aus {conv_dir}: {e}")

        # 2. Claude Code Projekte als Konversationen
        claude_dir = os.path.expanduser('~/.claude/projects')
        if os.path.isdir(claude_dir):
            try:
                for project_dir in sorted(os.listdir(claude_dir), reverse=True)[:5]:
                    project_path = os.path.join(claude_dir, project_dir)
                    if not os.path.isdir(project_path):
                        continue
                    for fname in sorted(os.listdir(project_path), reverse=True)[:3]:
                        if not fname.endswith('.jsonl'):
                            continue
                        fpath = os.path.join(project_path, fname)
                        try:
                            msg_count = sum(1 for _ in open(fpath, 'r', encoding='utf-8'))
                            conversations.append({
                                'session_key': f'claude-{project_dir}-{fname}',
                                'title': f'Claude: {project_dir[:40]}',
                                'summary': '',
                                'messages': [],
                                'message_count': msg_count,
                                'channel': 'claude-code',
                                'started_at': datetime.fromtimestamp(
                                    os.path.getmtime(fpath)).isoformat(),
                            })
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"Claude-Konversationen: {e}")

        return conversations[:20]

    def collect_scheduled_tasks(self) -> list:
        """Sammelt geplante Aufgaben (Crontab, Clawdbot-Tasks)."""
        tasks = []

        # 1. Crontab lesen
        try:
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.strip().split('\n')):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(None, 5)
                    if len(parts) >= 6:
                        schedule = ' '.join(parts[:5])
                        command = parts[5]
                        tasks.append({
                            'cron_job_id': f'cron-{i}',
                            'name': command[:80],
                            'schedule': schedule,
                            'text': line,
                            'is_enabled': True,
                        })
        except Exception as e:
            logger.debug(f"Crontab lesen: {e}")

        # 2. Clawdbot geplante Tasks aus Config
        task_files = [
            os.path.expanduser('~/.clawdbot/tasks.json'),
            os.path.join(self.workspace, 'tasks.json'),
            os.path.join(self.workspace, '.tasks.json'),
        ]
        for tf in task_files:
            if not os.path.exists(tf):
                continue
            try:
                with open(tf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for task in data if isinstance(data, list) else data.get('tasks', []):
                    tasks.append({
                        'cron_job_id': task.get('id', f'task-{len(tasks)}'),
                        'name': task.get('name', task.get('title', 'Unbekannt')),
                        'schedule': task.get('schedule', task.get('cron', '')),
                        'text': task.get('text', task.get('description', '')),
                        'is_enabled': task.get('enabled', True),
                    })
            except Exception as e:
                logger.debug(f"Tasks aus {tf}: {e}")

        # 3. Systemd Timer (Linux)
        if platform.system() == 'Linux':
            try:
                result = subprocess.run(
                    ['systemctl', '--user', 'list-timers', '--no-pager', '--plain'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Header ueberspringen
                        parts = line.split()
                        if len(parts) >= 5:
                            unit_name = parts[-1] if parts[-1].endswith('.timer') else ''
                            if unit_name:
                                tasks.append({
                                    'cron_job_id': f'systemd-{unit_name}',
                                    'name': unit_name.replace('.timer', ''),
                                    'schedule': 'systemd timer',
                                    'text': line.strip(),
                                    'is_enabled': True,
                                })
            except Exception:
                pass

        return tasks[:20]

    def _get_gateway_http_url(self) -> str:
        """Wandelt die Gateway-URL in eine HTTP-URL um."""
        url = self.gateway_url
        # ws://localhost:18789 -> http://localhost:18789
        if url.startswith('ws://'):
            url = 'http://' + url[5:]
        elif url.startswith('wss://'):
            url = 'https://' + url[6:]
        return url.rstrip('/')

    async def forward_to_gateway(self, model: str, messages: list) -> dict:
        """Leitet einen Chat-Request an den OpenClaw Gateway weiter (OpenAI-kompatible HTTP API)."""
        base_url = self._get_gateway_http_url()
        endpoint = f'{base_url}/v1/chat/completions'

        # OpenAI-kompatibles Request-Format
        payload = {
            'model': model or 'openclaw',
            'messages': messages,
        }

        body = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ClawboardConnector/1.0',
        }
        if self.openclaw_token:
            headers['Authorization'] = f'Bearer {self.openclaw_token}'

        req = urllib.request.Request(
            endpoint,
            data=body,
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode('utf-8'))

                # OpenAI-Format: choices[0].message.content
                if 'choices' in data and data['choices']:
                    content = data['choices'][0].get('message', {}).get('content', '')
                    return {'content': content}
                elif data.get('error'):
                    return {'error': str(data['error'])}
                else:
                    return {'content': str(data)}

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            logger.error(f"Gateway HTTP Fehler {e.code}: {error_body[:200]}")
            if e.code == 404:
                return {'error': 'Gateway /v1/chat/completions nicht verfuegbar. Aktiviere: openclaw config set gateway.http.endpoints.chatCompletions.enabled true'}
            elif e.code == 401:
                return {'error': 'Gateway Auth fehlgeschlagen. Pruefe openclaw_token in der Config.'}
            return {'error': f'Gateway HTTP {e.code}: {error_body[:200]}'}
        except urllib.error.URLError as e:
            return {'error': f'Gateway nicht erreichbar ({endpoint}): {e.reason}'}
        except Exception as e:
            return {'error': f'Gateway Fehler: {str(e)}'}

    async def process_chat_requests(self, chat_requests: list):
        """Verarbeitet Chat-Requests vom Server und leitet sie an den Gateway weiter."""
        for req in chat_requests:
            request_id = req.get('request_id')
            model = req.get('model', '')
            messages = req.get('messages', [])

            logger.info(f"Chat-Request #{request_id} -> Gateway ({model})")

            result = await self.forward_to_gateway(model, messages)

            response = {'request_id': request_id}
            if 'error' in result:
                response['error'] = result['error']
                logger.warning(f"Chat-Request #{request_id} Fehler: {result['error']}")
            else:
                response['content'] = result.get('content', '')
                logger.info(f"Chat-Request #{request_id} beantwortet ({len(response['content'])} Zeichen)")

            self.pending_chat_responses.append(response)

    async def collect_gateway_models(self) -> list:
        """Holt verfuegbare Modelle vom OpenClaw Gateway (HTTP API)."""
        now = time.time()
        if now - self.last_model_fetch < self.model_fetch_interval and self.cached_gateway_models:
            return self.cached_gateway_models

        # Manuelle Modelle aus Config als Fallback
        manual = self.config.get('manual_models', [])

        base_url = self._get_gateway_http_url()
        endpoint = f'{base_url}/v1/models'

        headers = {
            'User-Agent': 'ClawboardConnector/1.0',
        }
        if self.openclaw_token:
            headers['Authorization'] = f'Bearer {self.openclaw_token}'

        req = urllib.request.Request(endpoint, headers=headers, method='GET')

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

                models = []
                # OpenAI-Format: data[] mit id, owned_by etc.
                for m in data.get('data', data.get('models', [])):
                    model_id = m.get('id', '')
                    models.append({
                        'model_id': model_id,
                        'model_name': m.get('name', model_id),
                        'provider': m.get('owned_by', m.get('provider', '')),
                        'description': m.get('description', ''),
                        'is_available': True,
                    })

                if models:
                    self.cached_gateway_models = models
                    self.last_model_fetch = now
                    logger.info(f"{len(models)} Gateway-Modelle geladen")
                    return models

        except urllib.error.HTTPError as e:
            logger.debug(f"Gateway /v1/models HTTP {e.code}")
        except Exception as e:
            logger.debug(f"Gateway-Modelle nicht abrufbar: {e}")

        self.last_model_fetch = now
        return manual or self.cached_gateway_models

    def http_push(self, gateway_models=None) -> dict:
        """Daten per HTTP POST an Clawboard senden"""
        data = {
            'system': self.get_system_info(),
            'gateway': self.get_gateway_info(),
            'memory_files': self.collect_memory_files(),
            'skills': self.collect_skills(),
            'integrations': self.collect_integrations(),
            'projects': self.collect_projects(),
            'conversations': self.collect_conversations(),
            'scheduled_tasks': self.collect_scheduled_tasks(),
        }

        # Chat-Antworten mitsenden
        if self.pending_chat_responses:
            data['chat_responses'] = self.pending_chat_responses
            self.pending_chat_responses = []

        # Gateway-Modelle mitsenden
        if gateway_models:
            data['gateway_models'] = gateway_models

        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            self.push_url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.connection_token}',
                'User-Agent': 'ClawboardConnector/1.0',
            },
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            logger.error(f"HTTP Push Fehler {e.code}: {error_body}")
            return None
        except Exception as e:
            logger.error(f"HTTP Push Fehler: {e}")
            return None

    def handle_command(self, command: str):
        """Server-Befehl verarbeiten."""
        logger.info(f"Server-Befehl empfangen: {command}")
        if command == 'restart':
            logger.info("Neustart angefordert - lade Dateien neu und starte...")
            # connector.py und config.json neu herunterladen
            script_dir = os.path.dirname(os.path.abspath(__file__))
            base_url = self.push_url.rsplit('/api/', 1)[0]
            dl_url = base_url + '/connector/download/'
            try:
                req = urllib.request.Request(dl_url, headers={'User-Agent': 'ClawboardConnector/1.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    new_script = resp.read()
                with open(os.path.join(script_dir, 'connector.py'), 'wb') as f:
                    f.write(new_script)
                logger.info("connector.py aktualisiert")
            except Exception as e:
                logger.warning(f"connector.py Download fehlgeschlagen: {e}")
            # Prozess neustarten
            logger.info("Starte Prozess neu...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    async def run_http(self):
        """HTTP-basierter Push-Loop mit dynamischem Intervall und Chat-Support"""
        logger.info(f"HTTP Push Modus - Sende Daten an {self.push_url}")
        logger.info(f"Workspace: {self.workspace}")
        logger.info(f"Intervall: {self.heartbeat_interval}s (dynamisch bei Chat)")

        push_count = 0
        while self.running:
            # Gateway-Modelle periodisch abrufen
            gateway_models = await self.collect_gateway_models()

            result = self.http_push(gateway_models=gateway_models)
            push_count += 1

            if result and result.get('success'):
                conn_id = result.get('connection_id', '?')
                logger.info(f"Push #{push_count} erfolgreich (Connection: {conn_id})")

                # Server-Befehle pruefen
                cmd = result.get('command')
                if cmd:
                    self.handle_command(cmd)

                # OpenClaw Token vom Server uebernehmen
                server_token = result.get('openclaw_token', '')
                if server_token and server_token != self.openclaw_token:
                    self.openclaw_token = server_token
                    logger.info("OpenClaw Token vom Server aktualisiert")

                # Chat-Requests verarbeiten
                chat_requests = result.get('chat_requests', [])
                if chat_requests:
                    logger.info(f"{len(chat_requests)} Chat-Request(s) empfangen")
                    await self.process_chat_requests(chat_requests)
                    # Sofort Extra-Push mit Antworten
                    extra_result = self.http_push()
                    if extra_result and extra_result.get('success'):
                        logger.info("Chat-Antworten gesendet")

                # Dynamisches Push-Intervall
                server_interval = result.get('push_interval')
                if server_interval:
                    self.current_push_interval = server_interval
                else:
                    self.current_push_interval = self.heartbeat_interval
            else:
                logger.warning(f"Push #{push_count} fehlgeschlagen")

            await asyncio.sleep(self.current_push_interval)

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
        """Hauptloop - startet HTTP oder WebSocket Modus"""
        if self.mode == 'http':
            await self.run_http()
            return

        if not websockets:
            logger.error("WebSocket-Modus benoetigt 'websockets': pip install websockets")
            logger.info("Verwende --mode http als Alternative")
            return

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
        default_config = {
            'push_url': 'https://www.workloom.de/clawboard/api/push/',
            'workloom_url': 'wss://www.workloom.de/ws/clawboard/gateway/',
            'connection_token': 'DEIN-TOKEN-HIER',
            'gateway_url': 'ws://localhost:18789',
            'gateway_token': '',
            'openclaw_token': '',
            'heartbeat_interval': 30,
            'reconnect_delay': 10,
            'workspace': '~/clawd',
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
    parser.add_argument('--mode', '-m', choices=['http', 'ws'], default='http',
                        help='Verbindungsmodus: http (Standard) oder ws (WebSocket)')
    parser.add_argument('--debug', '-d', action='store_true', help='Debug-Modus')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(args.config)

    if config.get('connection_token') == 'DEIN-TOKEN-HIER':
        print("ERROR: Bitte trage deinen Connection Token in die Konfiguration ein!")
        print(f"Datei: {args.config or '~/.clawdbot/clawboard-connector.json'}")
        sys.exit(1)

    connector = ClawboardConnector(config, mode=args.mode)

    # Signal-Handler
    def signal_handler(sig, frame):
        connector.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Starten
    logger.info(f"Clawboard Connector gestartet (Modus: {args.mode})")
    asyncio.run(connector.run())
    logger.info("Clawboard Connector beendet")


if __name__ == '__main__':
    main()

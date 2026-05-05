"""Magvis Preflight-Stage: prüft alle System-Voraussetzungen vor Pipeline-Start.

Verhindert dass wir 18 Min Video rendern und dann scheitern, weil ein
externer Service down ist oder die Disk voll.

Geprüft:
1. Disk-Space (mindestens 5 GB frei in /var/www/workloom)
2. RAM (mindestens 1 GB frei)
3. Upload-Post.com API erreichbar (GET /uploadposts/users)
4. Gemini API erreichbar (Test-Call mit kleinem Payload)
5. OpenAI API erreichbar (models endpoint)
6. GLM/z.AI API erreichbar (chat-completion endpoint)
7. Shopify Admin-API erreichbar (shop endpoint)
8. Pexels API-Key gesetzt + erreichbar

Bei Fehler: Stage wirft Exception mit klarer Fehler-Meldung →
Pipeline bricht VOR dem teuren Video-Render ab.
"""
from __future__ import annotations

import logging
import shutil

import requests

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisPreflightCheck:
    """Pre-Flight-Checks vor jedem Magvis-Run."""

    MIN_DISK_FREE_GB = 5
    MIN_RAM_FREE_MB = 1024

    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user
        self.results = []  # Liste von (name, ok, message) Tupeln

    def run(self) -> dict:
        checks = [
            ('disk_space', self._check_disk_space),
            ('ram_free', self._check_ram),
            ('upload_post', self._check_upload_post),
            ('gemini', self._check_gemini),
            ('openai', self._check_openai),
            ('glm_zai', self._check_glm),
            ('shopify', self._check_shopify),
            ('pexels', self._check_pexels),
        ]
        for name, fn in checks:
            try:
                ok, msg = fn()
            except Exception as exc:
                ok, msg = False, f'Exception: {exc}'
            self.results.append((name, ok, msg))
            tag = '✓' if ok else '✗'
            self.project.log_stage('preflight', f'  {tag} {name}: {msg}')

        all_ok = all(r[1] for r in self.results)
        critical_failed = [r[0] for r in self.results if not r[1]]
        if not all_ok:
            raise RuntimeError(
                f'Preflight fehlgeschlagen — kritische Services nicht verfügbar: '
                f'{", ".join(critical_failed)}'
            )
        return {'success': True, 'checks': self.results}

    # -------------------------------------------------------------- checks

    def _check_disk_space(self) -> tuple[bool, str]:
        try:
            usage = shutil.disk_usage('/var/www/workloom')
            free_gb = usage.free / (1024 ** 3)
            ok = free_gb >= self.MIN_DISK_FREE_GB
            return ok, f'{free_gb:.1f} GB frei (min {self.MIN_DISK_FREE_GB})'
        except Exception as exc:
            return False, f'Disk-Check-Error: {exc}'

    def _check_ram(self) -> tuple[bool, str]:
        try:
            with open('/proc/meminfo') as f:
                meminfo = {line.split(':')[0]: line.split(':')[1].strip()
                           for line in f if ':' in line}
            avail_kb = int(meminfo.get('MemAvailable', '0').split()[0])
            avail_mb = avail_kb // 1024
            ok = avail_mb >= self.MIN_RAM_FREE_MB
            return ok, f'{avail_mb} MB frei (min {self.MIN_RAM_FREE_MB})'
        except Exception as exc:
            return False, f'RAM-Check-Error: {exc}'

    def _check_upload_post(self) -> tuple[bool, str]:
        api_key = (getattr(self.user, 'upload_post_api_key', None)
                   or getattr(self.user, 'uploadpost_api_key', None))
        if not api_key:
            return False, 'API-Key fehlt'
        try:
            r = requests.get(
                'https://api.upload-post.com/api/uploadposts/users',
                headers={'Authorization': f'Apikey {api_key.strip()}'},
                timeout=15,
            )
            if r.status_code == 200:
                return True, 'erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except requests.exceptions.SSLError as exc:
            return False, f'SSL-Error: {str(exc)[:80]}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

    def _check_gemini(self) -> tuple[bool, str]:
        api_key = (getattr(self.user, 'gemini_api_key', None)
                   or getattr(self.user, 'google_api_key', None))
        if not api_key:
            return False, 'API-Key fehlt'
        try:
            r = requests.get(
                'https://generativelanguage.googleapis.com/v1beta/models',
                params={'key': api_key},
                timeout=15,
            )
            if r.status_code == 200:
                return True, 'erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

    def _check_openai(self) -> tuple[bool, str]:
        api_key = getattr(self.user, 'openai_api_key', None)
        if not api_key:
            return False, 'API-Key fehlt'
        try:
            r = requests.get(
                'https://api.openai.com/v1/models',
                headers={'Authorization': f'Bearer {api_key.strip()}'},
                timeout=15,
            )
            if r.status_code == 200:
                return True, 'erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

    def _check_glm(self) -> tuple[bool, str]:
        from ..models import MagvisSettings
        ms = MagvisSettings.objects.filter(user=self.user).first()
        api_key = getattr(self.user, 'zhipu_api_key', None)
        if not api_key:
            return False, 'zhipu_api_key fehlt'
        base = (ms.glm_base_url if ms else '') or 'https://api.z.ai/api/coding/paas/v4'
        try:
            # Cheapest possible call: 1-token chat completion
            r = requests.post(
                f'{base}/chat/completions',
                headers={'Authorization': f'Bearer {api_key.strip()}',
                         'Content-Type': 'application/json'},
                json={
                    'model': (ms.glm_model if ms else 'glm-5.1'),
                    'messages': [{'role': 'user', 'content': 'hi'}],
                    'max_tokens': 1,
                },
                timeout=20,
            )
            if r.status_code == 200:
                return True, 'erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

    def _check_shopify(self) -> tuple[bool, str]:
        try:
            from ploom.models import PLoomSettings
            ps = PLoomSettings.objects.filter(user=self.user).first()
            if not ps or not ps.default_store:
                return False, 'kein Shopify-Store konfiguriert'
            store = ps.default_store
            r = requests.get(
                f'https://{store.shop_domain}/admin/api/2023-10/shop.json',
                headers={'X-Shopify-Access-Token': store.access_token},
                timeout=15,
            )
            if r.status_code == 200:
                return True, f'{store.shop_domain} erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

    def _check_pexels(self) -> tuple[bool, str]:
        # Pexels-Key über vidgen — schauen ob er gesetzt ist
        try:
            from django.conf import settings as django_settings
            api_key = getattr(django_settings, 'PEXELS_API_KEY', None) or ''
            if not api_key:
                # Aus User-Settings probieren
                api_key = getattr(self.user, 'pexels_api_key', '') or ''
            if not api_key:
                return False, 'API-Key fehlt (PEXELS_API_KEY in settings)'
            r = requests.get(
                'https://api.pexels.com/videos/search',
                params={'query': 'test', 'per_page': 1},
                headers={'Authorization': api_key.strip()},
                timeout=15,
            )
            if r.status_code == 200:
                return True, 'erreichbar (200)'
            return False, f'HTTP {r.status_code}'
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

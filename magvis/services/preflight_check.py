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
import time

import requests

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisPreflightCheck:
    """Pre-Flight-Checks vor jedem Magvis-Run."""

    MIN_DISK_FREE_GB = 5
    MIN_RAM_FREE_MB = 1024
    HTTP_RETRIES = 3
    HTTP_BACKOFF_BASE_S = 1.0  # 1s, 2s, 4s zwischen Versuchen

    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user
        self.results = []  # Liste von (name, ok, message) Tupeln

    def _http_with_retry(self, request_fn) -> tuple[bool, str]:
        """Fuehrt HTTP-Call mit Retry + exponential backoff aus.

        Verhindert transient outages (z.B. Z.AI 13s+ Latenz, OpenAI 5xx)
        eine ganze Pipeline zu stoppen.

        request_fn: callable -> requests.Response (oder raise).
        Liefert (ok, msg). ok=True nur bei status 200.
        """
        last_err = ''
        for attempt in range(1, self.HTTP_RETRIES + 1):
            try:
                r = request_fn()
                if r.status_code == 200:
                    suffix = f' (Versuch {attempt})' if attempt > 1 else ''
                    return True, f'erreichbar (200){suffix}'
                last_err = f'HTTP {r.status_code}'
            except Exception as exc:
                last_err = f'{type(exc).__name__}: {str(exc)[:80]}'
            if attempt < self.HTTP_RETRIES:
                time.sleep(self.HTTP_BACKOFF_BASE_S * (2 ** (attempt - 1)))
        return False, f'{last_err} (nach {self.HTTP_RETRIES} Versuchen)'

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
        return self._http_with_retry(lambda: requests.get(
            'https://api.upload-post.com/api/uploadposts/users',
            headers={'Authorization': f'Apikey {api_key.strip()}'},
            timeout=20,
        ))

    def _check_gemini(self) -> tuple[bool, str]:
        api_key = (getattr(self.user, 'gemini_api_key', None)
                   or getattr(self.user, 'google_api_key', None))
        if not api_key:
            return False, 'API-Key fehlt'
        return self._http_with_retry(lambda: requests.get(
            'https://generativelanguage.googleapis.com/v1beta/models',
            params={'key': api_key},
            timeout=20,
        ))

    def _check_openai(self) -> tuple[bool, str]:
        api_key = getattr(self.user, 'openai_api_key', None)
        if not api_key:
            return False, 'API-Key fehlt'
        return self._http_with_retry(lambda: requests.get(
            'https://api.openai.com/v1/models',
            headers={'Authorization': f'Bearer {api_key.strip()}'},
            timeout=20,
        ))

    def _check_glm(self) -> tuple[bool, str]:
        # GLM/Z.AI hat oft 10-30s Latenz auf chat-completions — Timeout 60s,
        # plus 3 Retries mit Backoff — wenn der Service kurz hustet, machen
        # wir die Pipeline nicht kaputt.
        from ..models import MagvisSettings
        ms = MagvisSettings.objects.filter(user=self.user).first()
        api_key = getattr(self.user, 'zhipu_api_key', None)
        if not api_key:
            return False, 'zhipu_api_key fehlt'
        base = (ms.glm_base_url if ms else '') or 'https://api.z.ai/api/coding/paas/v4'
        model = (ms.glm_model if ms else 'glm-5.1')
        ok, msg = self._http_with_retry(lambda: requests.post(
            f'{base}/chat/completions',
            headers={'Authorization': f'Bearer {api_key.strip()}',
                     'Content-Type': 'application/json'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': 'hi'}],
                'max_tokens': 1,
            },
            timeout=60,
        ))
        # Transiente Z.AI-Ueberlastung (HTTP 429 / Code 1305) ist NICHT kritisch:
        # Pipeline nicht killen und keine Alert-Mail spammen — laeuft mit Backoff weiter.
        if not ok and '429' in (msg or ''):
            return True, f'Z.AI ueberlastet (429, nicht-kritisch): {(msg or "")[:80]}'
        return ok, msg

    def _check_shopify(self) -> tuple[bool, str]:
        from ploom.models import PLoomSettings
        ps = PLoomSettings.objects.filter(user=self.user).first()
        if not ps or not ps.default_store:
            return False, 'kein Shopify-Store konfiguriert'
        store = ps.default_store
        ok, msg = self._http_with_retry(lambda: requests.get(
            f'https://{store.shop_domain}/admin/api/2023-10/shop.json',
            headers={'X-Shopify-Access-Token': store.access_token},
            timeout=20,
        ))
        if ok:
            return True, f'{store.shop_domain} {msg}'
        return ok, msg

    def _check_pexels(self) -> tuple[bool, str]:
        from django.conf import settings as django_settings
        api_key = getattr(django_settings, 'PEXELS_API_KEY', None) or ''
        if not api_key:
            api_key = getattr(self.user, 'pexels_api_key', '') or ''
        if not api_key:
            return False, 'API-Key fehlt (PEXELS_API_KEY in settings)'
        try:
            return self._http_with_retry(lambda: requests.get(
                'https://api.pexels.com/videos/search',
                params={'query': 'test', 'per_page': 1},
                headers={'Authorization': api_key.strip()},
                timeout=20,
            ))
        except Exception as exc:
            return False, f'{type(exc).__name__}: {str(exc)[:80]}'

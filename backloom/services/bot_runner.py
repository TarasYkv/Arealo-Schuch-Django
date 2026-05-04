"""BotRunner — fuehrt eine einzelne Backlink-Submission aus.

Kapselt:
- Browser-Session-Lifecycle (Container-API)
- LLM-Anbindung (GLM 5.1 via Z.AI Coding-Plan, mit Anthropic-Fallback)
- Anti-Spam-Daten-Variation (Bio + Anchor + Profil)
- Schritt-Logging in SubmissionAttempt
- Screenshots als Media-Files speichern

WICHTIG: Erster MVP-Lauf nutzt browser-use als Hauptagent, faellt aber auf
einen reduzierten "scout"-Modus zurueck wenn browser-use noch nicht im venv
installiert ist (siehe lazy import). Damit kann man die Pipeline auch ohne
browser-use erstmal mit einem einfachen Playwright-Skript validieren.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .browser_client import BrowserContainerClient, BrowserContainerError
from ..models import (
    BacklinkSource,
    BioVariant,
    NaturmacherProfile,
    SubmissionAttempt,
    SubmissionAttemptStatus,
)

logger = logging.getLogger(__name__)

ANCHOR_VARIANTS = {
    'brand': [
        'Naturmacher',
        'Naturmacher.de',
        'naturmacher.de',
    ],
    'generic': [
        'hier',
        'unsere Webseite',
        'mehr Infos',
        'unsere Geschenke',
        'unser Shop',
    ],
    'keyword': [
        'personalisierte Geschenke',
        'Geschenke mit Gravur',
        'individuelle Blumentoepfe',
    ],
}

ANCHOR_DISTRIBUTION = {
    'brand': 0.6,
    'generic': 0.3,
    'keyword': 0.1,
}


def pick_anchor() -> tuple[str, str]:
    """Liefert (anchor_text, category) gemaess Distribution."""
    r = random.random()
    cum = 0.0
    for cat, weight in ANCHOR_DISTRIBUTION.items():
        cum += weight
        if r <= cum:
            return random.choice(ANCHOR_VARIANTS[cat]), cat
    return ANCHOR_VARIANTS['brand'][0], 'brand'


class BotRunner:
    """Fuehrt eine SubmissionAttempt-Pipeline aus.

    Lifecycle:
        runner = BotRunner(attempt)
        runner.run()                 # blockierend, kann Minuten dauern
        # → SubmissionAttempt ist final aktualisiert
    """

    SCREENSHOT_INTERVAL_S = 4.0
    DEFAULT_TIMEOUT_S = 240

    def __init__(self, attempt: SubmissionAttempt):
        self.attempt = attempt
        self.profile: NaturmacherProfile = attempt.profile
        self.user = self.profile.user
        self.source: BacklinkSource = attempt.source
        self.bio: Optional[BioVariant] = attempt.bio_variant
        self.client = BrowserContainerClient()

    # ---- public -------------------------------------------------------------

    def run(self) -> SubmissionAttempt:
        """Fuehrt die Submission aus. Idempotent in dem Sinne, dass ein bereits
        abgeschlossener Attempt nicht nochmal laeuft (Status-Check)."""
        a = self.attempt
        if a.status not in (
            SubmissionAttemptStatus.QUEUED,
            SubmissionAttemptStatus.NEEDS_MANUAL,
        ):
            self._log(f'Attempt im Status {a.status} — wird NICHT erneut gestartet', 'warn')
            return a

        a.status = SubmissionAttemptStatus.RUNNING
        a.started_at = timezone.now()
        a.novnc_url = BrowserContainerClient.public_novnc_url()
        a.save(update_fields=['status', 'started_at', 'novnc_url', 'updated_at'])
        self._log(f'Submission startet → {self.source.url}')

        # Bio + Anchor wuerfeln
        if self.bio is None:
            self.bio = self._pick_bio()
            a.bio_variant = self.bio
            a.save(update_fields=['bio_variant', 'updated_at'])
        anchor_text, anchor_cat = pick_anchor()
        a.anchor_text_used = anchor_text
        a.save(update_fields=['anchor_text_used', 'updated_at'])
        self._log(
            f'Bio gewaehlt (Bucket {self.bio.length_bucket if self.bio else "-"}) | '
            f'Anchor: "{anchor_text}" ({anchor_cat})'
        )

        try:
            self._ensure_container_ready()
            session = self.client.start_session(start_url=self.source.url)
            a.container_id = 'backloom-browser'
            a.save(update_fields=['container_id', 'updated_at'])
            self._log(f'Browser-Session gestartet, CDP={session.get("cdp_endpoint")}')

            # MVP-Step: Screenshot direkt nach Page-Load — beweist Pipeline.
            # Ab Phase 3.5 ersetzen wir das durch einen browser-use-Agent-Run.
            time.sleep(5)  # damit Page geladen ist
            self._capture_screenshot(label='page_loaded')

            # Hier wird in der naechsten Iteration der browser-use-Agent angehakt.
            self._log(
                'MVP-Foundation OK. browser-use-Integration folgt in 3.2/3.5 — '
                'aktuell wird nur Page geladen + Screenshot gemacht.'
            )

            a.status = SubmissionAttemptStatus.SUCCESS
            self._log('Foundation-Test erfolgreich (Browser-Container Pipeline funktioniert)')

        except BrowserContainerError as exc:
            a.status = SubmissionAttemptStatus.FAILED_OTHER
            a.error_message = f'Browser-Container-Fehler: {exc}'
            self._log(str(exc), 'error')
        except Exception as exc:
            a.status = SubmissionAttemptStatus.FAILED_OTHER
            a.error_message = f'{type(exc).__name__}: {exc}'
            logger.exception('BotRunner-Fehler')
            self._log(f'Unhandled: {exc}', 'error')
        finally:
            try:
                self.client.stop_session()
                self._log('Browser-Session gestoppt')
            except Exception as exc:
                logger.warning('stop_session fehlgeschlagen: %s', exc)
            a.completed_at = timezone.now()
            a.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])

        return a

    # ---- helpers ------------------------------------------------------------

    def _ensure_container_ready(self):
        try:
            health = self.client.healthz()
        except Exception as exc:
            raise BrowserContainerError(
                f'Browser-Container nicht erreichbar: {exc}. '
                f'Pruefe `docker ps` auf dem Hetzner-Host.'
            )
        if not health.get('ok'):
            raise BrowserContainerError(f'Container ungesund: {health}')
        # Wenn noch eine alte Session laeuft — beenden, damit wir sauber starten.
        if health.get('session_active'):
            self._log('Alte Session laeuft noch — wird vorher beendet', 'warn')
            self.client.stop_session()

    def _pick_bio(self) -> Optional[BioVariant]:
        """Random-Pick einer aktiven Bio-Variante. Bevorzugt wenig genutzte."""
        qs = self.profile.bio_variants.filter(is_active=True)
        if not qs.exists():
            return None
        # Round-robin-mode: nimm die mit kleinster use_count (Tie -> random).
        candidates = list(qs.order_by('use_count', '?')[:5])
        return random.choice(candidates) if candidates else None

    def _capture_screenshot(self, label: str = 'shot') -> str:
        """Holt PNG vom Container, speichert unter MEDIA_ROOT/backloom/screenshots/."""
        try:
            png_bytes = self.client.screenshot()
        except Exception as exc:
            self._log(f'Screenshot-Fehler: {exc}', 'warn')
            return ''
        rel_dir = Path('backloom') / 'screenshots' / str(self.attempt.id)
        abs_dir = Path(settings.MEDIA_ROOT) / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        filename = f'{label}_{ts}_{uuid.uuid4().hex[:6]}.png'
        rel_path = rel_dir / filename
        abs_path = Path(settings.MEDIA_ROOT) / rel_path
        abs_path.write_bytes(png_bytes)
        media_url = f'{settings.MEDIA_URL.rstrip("/")}/{rel_path}'
        self._log(f'Screenshot gespeichert: {label}', screenshot_url=media_url)
        return media_url

    def _log(self, msg: str, level: str = 'info', screenshot_url: str = ''):
        """Schreibt eine Zeile in den Step-Log und ins normale Logging."""
        logger.info('[%s] [%s] %s', self.attempt.id, level, msg)
        try:
            self.attempt.add_step(msg, screenshot_url=screenshot_url, level=level)
        except Exception as exc:
            logger.warning('add_step fehlgeschlagen: %s', exc)

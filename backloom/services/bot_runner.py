"""BotRunner — fuehrt eine einzelne Backlink-Submission aus.

Kapselt:
- Browser-Session-Lifecycle (Container-API)
- LLM-Anbindung (GLM 5.1 via Z.AI Coding-Plan, mit Anthropic-Fallback)
- Anti-Spam-Daten-Variation (Bio + Anchor + Profil)
- Schritt-Logging in SubmissionAttempt
- Screenshots als Media-Files speichern

Phase 3.5 nutzt **browser-use** als AI-Agent, der via CDP an den im
Browser-Container laufenden Chromium attached. Wenn browser-use im venv
fehlt oder fehlschlaegt, faellt der Runner auf einen reinen "Page-Load +
Screenshot"-Modus zurueck (Foundation-Test, beweist nur die Pipeline).
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
from .captcha_cascade import (
    CaptchaCascade, CaptchaContext, CaptchaKind, CaptchaSolution,
)
from ..models import (
    BacklinkSource,
    BioVariant,
    ControlledBy,
    NaturmacherProfile,
    SubmissionAttempt,
    SubmissionAttemptStatus,
)


# JavaScript das im Browser laeuft um Captchas zu erkennen.
# Liefert {kind, site_key, page_url} per page.evaluate().
CAPTCHA_DETECT_JS = r"""
(() => {
  const result = {kind: 'none', site_key: '', invisible: false, enterprise: false};
  // reCAPTCHA v2 (sichtbar oder invisible)
  const recaptcha = document.querySelector('.g-recaptcha[data-sitekey], iframe[src*="recaptcha/api2/anchor"], iframe[src*="recaptcha/enterprise/anchor"]');
  if (recaptcha) {
    const widget = document.querySelector('.g-recaptcha[data-sitekey]');
    if (widget) {
      result.site_key = widget.getAttribute('data-sitekey') || '';
      result.invisible = (widget.getAttribute('data-size') === 'invisible');
    } else {
      const iframe = recaptcha;
      const m = iframe.src.match(/[?&]k=([^&]+)/);
      if (m) result.site_key = decodeURIComponent(m[1]);
      result.invisible = /size=invisible/.test(iframe.src);
      result.enterprise = /enterprise/.test(iframe.src);
    }
    result.kind = 'recaptcha_v2';
    return result;
  }
  // reCAPTCHA v3 — als versteckter Token, oft an forms gebunden
  if (window.grecaptcha && document.querySelector('script[src*="recaptcha/api.js?render="]')) {
    const m = (document.documentElement.outerHTML.match(/render=([\w\-]+)/) || [])[1];
    if (m) { result.kind = 'recaptcha_v3'; result.site_key = m; return result; }
  }
  // hCaptcha
  const hcaptcha = document.querySelector('.h-captcha[data-sitekey], iframe[src*="hcaptcha.com"]');
  if (hcaptcha) {
    const widget = document.querySelector('.h-captcha[data-sitekey]');
    if (widget) result.site_key = widget.getAttribute('data-sitekey') || '';
    else {
      const m = hcaptcha.src && hcaptcha.src.match(/[?&]sitekey=([^&]+)/);
      if (m) result.site_key = decodeURIComponent(m[1]);
    }
    result.kind = 'hcaptcha'; return result;
  }
  // Cloudflare Turnstile
  const turnstile = document.querySelector('.cf-turnstile[data-sitekey], iframe[src*="challenges.cloudflare.com"]');
  if (turnstile) {
    const widget = document.querySelector('.cf-turnstile[data-sitekey]');
    if (widget) result.site_key = widget.getAttribute('data-sitekey') || '';
    result.kind = 'turnstile'; return result;
  }
  // Cloudflare-Challenge (volle Seite)
  if (document.title.includes('Just a moment') || document.querySelector('#challenge-form')) {
    result.kind = 'cloudflare'; return result;
  }
  return result;
})()
"""

# JavaScript um den Captcha-Token einzuspeisen (reCAPTCHA / hCaptcha)
CAPTCHA_INJECT_JS = r"""
(token, kind) => {
  if (!token) return false;
  if (kind === 'recaptcha_v2' || kind === 'recaptcha_v3') {
    document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(el => {
      el.value = token; el.style.display = 'block';
    });
    if (window.___grecaptcha_cfg) {
      Object.entries(window.___grecaptcha_cfg.clients || {}).forEach(([id, c]) => {
        try {
          for (const k of Object.keys(c)) {
            const obj = c[k];
            if (obj && obj.callback) obj.callback(token);
          }
        } catch (e) {}
      });
    }
    return true;
  }
  if (kind === 'hcaptcha') {
    document.querySelectorAll('textarea[name="h-captcha-response"]').forEach(el => {
      el.value = token; el.style.display = 'block';
    });
    return true;
  }
  if (kind === 'turnstile') {
    document.querySelectorAll('input[name="cf-turnstile-response"]').forEach(el => {
      el.value = token;
    });
    return true;
  }
  return false;
}
"""

# Z.AI Coding Plan Endpoint (selbe URL wie magvis/llm_providers.py:zhipu)
ZAI_BASE_URL = 'https://api.z.ai/api/coding/paas/v4'

# Default Modell — der Coding Plan billt unabhaengig vom Modell, also
# nehmen wir das staerkste fuer Browser-Tasks (Vision + Reasoning).
GLM_MODEL = 'glm-4.6'  # Fallback
GLM_MODEL_PRIMARY = 'glm-5.1'  # bevorzugt

# Wie viele Schritte darf der Agent maximal machen, bevor abgebrochen wird?
MAX_AGENT_STEPS = 25

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
            cdp_url = session.get('cdp_endpoint', '')
            a.container_id = 'backloom-browser'
            a.save(update_fields=['container_id', 'updated_at'])
            self._log(f'Browser-Session gestartet, CDP={cdp_url}')

            # Page erstmal kurz settlen lassen damit der initial-load Screenshot
            # nicht eine weisse Seite zeigt
            time.sleep(3)
            self._capture_screenshot(label='page_loaded')

            # Wenn Source einen Submission-Task hat (gelernt oder vom User
            # gesetzt), uebergeben wir den. Sonst nehmen wir einen Standard-Task
            # der "registrieren" generisch beschreibt — fuer Foundation-Tests reicht das.
            agent_task = self._build_agent_task()

            try:
                agent_result = asyncio.run(self._run_browser_use(cdp_url, agent_task))
                self._log(f'browser-use Agent fertig: {agent_result.get("done", False)}')
                if agent_result.get('done'):
                    # Bot meldet success — aber wir glauben das erst wenn der
                    # Link auf der Source-Seite tatsaechlich existiert.
                    a.status = SubmissionAttemptStatus.PENDING_VERIFY
                    candidate_url = agent_result.get('backlink_url', '') or ''
                    a.backlink_url = candidate_url
                    a.save(update_fields=['status', 'backlink_url', 'updated_at'])
                    self._log(
                        f'Bot meldet Erfolg → starte Link-Verifizierung '
                        f'(URL: {candidate_url[:80] or "—"})',
                        'info',
                    )
                    self._run_link_verification(candidate_url)
                    # Email-Confirmation nur wenn Link verifiziert wurde
                    if a.status == SubmissionAttemptStatus.SUCCESS:
                        self._run_email_verification()
                else:
                    # Sonderfall: Bot hat erkannt dass Email bereits registriert ist
                    final_text = (agent_result.get('final', '') or '').upper()
                    if 'ALREADY_REGISTERED' in final_text:
                        a.status = SubmissionAttemptStatus.ALREADY_REGISTERED
                        a.error_message = agent_result.get('final', '')[:400]
                        a.save(update_fields=['status', 'error_message', 'updated_at'])
                        # Source als "schon abgehakt" markieren, nicht skipped
                        try:
                            from ..models import BacklinkSource
                            self.source.is_processed = True
                            self.source.notes = (
                                (self.source.notes or '') +
                                '\n[Bot] Account war schon registriert — Site uebersprungen'
                            ).strip()
                            self.source.save(update_fields=['is_processed', 'notes', 'updated_at'])
                        except Exception:
                            pass
                        self._log(
                            'Site meldet "Email bereits registriert" → '
                            'Status ALREADY_REGISTERED, kein Wait-Loop',
                            'info',
                        )
                        return a
                    a.status = SubmissionAttemptStatus.NEEDS_MANUAL
                    a.save(update_fields=['status', 'updated_at'])
                    self._log('Agent ist nicht "done" gegangen — manuelles Eingreifen empfohlen', 'warn')
                    # Browser bleibt OFFEN — User kann ueber noVNC eingreifen.
                    self._wait_for_user_intervention()
            except _BrowserUseUnavailable as exc:
                # Soft-Fallback: nur Foundation-Test, kein echter Submit
                a.status = SubmissionAttemptStatus.SUCCESS
                self._log(
                    f'browser-use nicht nutzbar ({exc}) — Lauf endet als Foundation-Test '
                    f'(nur Page geladen + Screenshot)',
                    'warn',
                )
            except Exception as exc:
                a.status = SubmissionAttemptStatus.FAILED_OTHER
                a.error_message = f'browser-use-Fehler: {type(exc).__name__}: {exc}'
                logger.exception('browser-use-Fehler')
                self._log(str(exc), 'error')

            self._capture_screenshot(label='final')

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
            a.save(update_fields=['status', 'backlink_url', 'error_message',
                                  'completed_at', 'updated_at'])

        return a

    # ---- agent-task ----------------------------------------------------------

    def _build_agent_task(self) -> str:
        """Baut die natuerlichsprachige Aufgabe fuer den browser-use-Agent."""
        p = self.profile
        bio_text = self.bio.text if self.bio else ''
        anchor = self.attempt.anchor_text_used or 'Naturmacher'

        return (
            f'Du bist auf der Seite {self.source.url}.\n\n'
            f'AUFGABE: Trage die Firma "{p.firma}" in dieses Verzeichnis ein, '
            f'so dass am Ende ein FUNKTIONIERENDER OEFFENTLICHER PROFIL-LINK existiert.\n\n'
            f'⚠️ KRITISCH — TYPISCHER ZWEISTUFIGER FLOW:\n'
            f'1. Account registrieren (Email + Passwort + ggf. Captcha)\n'
            f'2. **DANACH** ein separates "Firma eintragen" / "Eintrag erstellen" / '
            f'   "Mein Eintrag" / "Profil ausfuellen"-Formular ausfuellen\n\n'
            f'Eine erfolgreiche Registrierung ALLEIN reicht NICHT — das erzeugt nur '
            f'einen Login, aber KEINEN oeffentlichen Eintrag und damit KEINEN Backlink.\n\n'
            f'NACH DER REGISTRIERUNG ist deine Aufgabe NICHT FERTIG. Suche aktiv nach '
            f'Buttons/Links mit Begriffen wie:\n'
            f'  • "Firma eintragen", "Eintrag erstellen", "Eintrag hinzufuegen"\n'
            f'  • "Profil ausfuellen", "Mein Profil bearbeiten", "Branche eintragen"\n'
            f'  • "Add Listing", "Create Entry", "Submit Business"\n'
            f'Klicke und fuelle dieses Formular aus — DAS ist der Backlink-erzeugende Schritt.\n\n'
            f'ERFOLGS-KRITERIUM (nur dann done(success=true) aufrufen):\n'
            f'1. Du siehst eine Bestaetigungsmeldung "Eintrag gespeichert", '
            f'  "Erfolgreich veroeffentlicht" o.ae. ODER eine Erfolgs-Page\n'
            f'2. **NAVIGIERE ZUR OEFFENTLICHEN PROFILSEITE**:\n'
            f'   - Suche Buttons/Links: "Profil ansehen", "Eintrag ansehen",\n'
            f'     "Vorschau", "View public profile", "Zur Firmenseite"\n'
            f'   - Klicke darauf — die URL muss eine OEFFENTLICHE sein (nicht\n'
            f'     /mein-konto, /dashboard, /admin, /account)\n'
            f'3. **VERIFIZIERE die public URL ohne Login**: Optional ein '
            f'   incognito/neuer-Tab-Test ist nicht moeglich, aber pruefe ob auf '
            f'   dieser Seite der Naturmacher-Eintrag mit Link sichtbar ist\n'
            f'4. **GIB DIE PUBLIC URL als done()-Result zurueck**:\n'
            f'   z.B. done(success=true, text="https://example.com/firmen/'
            f'naturmacher-bensheim")\n'
            f'   NICHT die /mein-konto-URL!\n\n'
            f'Wenn du:\n'
            f'- Nur registriert hast → done(success=false)\n'
            f'- Eintrag gespeichert aber keine oeffentliche URL gefunden\n'
            f'  → done(success=false, text="Eintrag gespeichert aber Profilseite '
            f'  nicht erreichbar — evtl. Moderation pending")\n'
            f'- Gemerkt dass /mein-konto Login-walled ist und keinen "Profil ansehen"-'
            f'  Button hat → done(success=false, text=...)\n'
            f'- **Site meldet "Email bereits registriert" / "Account existiert bereits" / '
            f'  "Diese E-Mail-Adresse wird bereits verwendet" / "user already exists" '
            f'  → SOFORT abbrechen mit done(success=false, text="ALREADY_REGISTERED: '
            f'  <kurze Erklaerung>"). KEIN Versuch sich einzuloggen — wir wissen das '
            f'  Passwort eines etwaig vorhandenen Accounts nicht zwingend, und wir '
            f'  wollen ein klares Signal dass diese Site schon abgehakt ist**\n\n'
            f'WICHTIG:\n'
            f'- Im Beschreibungs-/Bio-Feld nutze EXAKT diesen Text:\n'
            f'  "{bio_text}"\n'
            f'- Als Link-Text (anchor) verwende "{anchor}"\n'
            f'- Fuelle ALLE Felder aus, auch optionale (Leistungen, Oeffnungszeiten, '
            f'  Tags, Kategorien, Logo-URL etc.) — siehe ZUSATZDATEN unten.\n'
            f'- Wenn ein Captcha auftritt, mach NICHTS und gib auf — der Mensch loest es.\n'
            f'- Wenn die Seite eine Email-Bestaetigung verlangt, mache so weit wie '
            f'  moeglich (bis zur Bestaetigungs-Mail-Anforderung) und beende.\n'
            f'- Cookie-Banner: alle akzeptieren, damit der Flow weitergeht.\n\n'
            f'ZUSATZDATEN (fuer optionale Felder):\n'
            f'- Leistungen/Services: '
            f'"Lasergravur, Personalisierte Blumentoepfe, Geschenke mit Gravur, '
            f'Hochzeitsgeschenke, Geburtstagsgeschenke, Wunschgravur, Made in Germany"\n'
            f'- Oeffnungszeiten: "Online-Shop 24/7 verfuegbar; Werkstatt nach Vereinbarung"\n'
            f'- Tags/Schlagworte: "{p.keywords or "personalisierte Geschenke, Lasergravur, Blumentopf"}"\n'
            f'- Logo-URL: "{p.website}/cdn/shop/files/logo.png" (falls Logo-Feld optional)\n'
            f'- Gruendungsjahr / Established: 2018\n'
            f'- Anzahl Mitarbeiter: 1-10\n'
            f'- Liefergebiet: Deutschland, Oesterreich, Schweiz, EU\n'
            f'- Zahlungsarten: Kreditkarte, PayPal, Klarna, Vorkasse, Rechnung\n'
            f'- Versand: DHL, Kostenloser Versand ab 50 Euro\n\n'
            f'DATEN ZUM EINTRAGEN:\n'
            f'- Firma: {p.firma}\n'
            f'- Inhaber/Ansprechperson: {p.inhaber}\n'
            f'- Webseite: {p.website}\n'
            f'- Email (fuer Registrierungen): {p.email}\n'
            f'- Telefon: {p.telefon}\n'
            f'- Strasse: {p.strasse}\n'
            f'- PLZ: {p.plz}\n'
            f'- Ort: {p.ort}\n'
            f'- Land: {p.land}\n'
            f'- USt-IdNr: {p.ust_id}\n'
            f'- Kategorie: {p.kategorie}\n'
            f'- Default-Username: {p.default_username}\n'
            f'- Default-Passwort: {p.default_password}\n\n'
            f'Wenn das Formular abgeschickt wurde und du eine Erfolgsmeldung siehst '
            f'(z.B. "Vielen Dank", "Eintrag wurde erstellt", "Bestaetigungs-Email versendet"), '
            f'beende den Task mit "done" und gib die finale URL zurueck.'
        )

    async def _run_browser_use(self, cdp_url: str, task: str) -> dict:
        """Startet einen browser-use-Agent gegen die laufende CDP-Session."""
        try:
            from browser_use import Agent, BrowserSession, ChatOpenAI
        except Exception as exc:
            raise _BrowserUseUnavailable(f'import fehlgeschlagen: {exc}')

        glm_key = self.user.zhipu_api_key
        if not glm_key:
            raise _BrowserUseUnavailable('Kein zhipu_api_key beim User gesetzt')

        # ChatOpenAI in browser-use nimmt OpenAI-kompatible Endpoints,
        # ueber die ENV-Vars die das interne openai-SDK nutzt.
        os.environ['OPENAI_API_KEY'] = glm_key
        os.environ['OPENAI_BASE_URL'] = ZAI_BASE_URL
        llm = ChatOpenAI(model=GLM_MODEL_PRIMARY, temperature=0.2)

        self._log(f'Initialisiere browser-use mit Modell {GLM_MODEL_PRIMARY} via Z.AI', 'info')

        # browser-use will den HTTP-Discover-Endpoint (z.B. http://host:9222)
        # — die Control-API liefert direkt den ws://-Endpoint, der ist fuer
        # den initialen Discovery-Call ungeeignet.
        cdp_http = 'http://127.0.0.1:9222'
        session = BrowserSession(cdp_url=cdp_http)
        # Hook der nach jedem Step prueft, ob ein Captcha erschienen ist und
        # ggf. die Cascade aufruft.
        on_step_callback = self._make_captcha_step_callback(session)

        agent = Agent(task=task, llm=llm, browser_session=session,
                       register_new_step_callback=on_step_callback)

        try:
            result = await agent.run(max_steps=MAX_AGENT_STEPS)
        except Exception as exc:
            self._log(f'agent.run-Fehler: {exc}', 'error')
            raise

        # Schema einer browser-use AgentHistoryList:
        # - is_done(): Agent rief done-Action (kann success=True ODER False sein!)
        # - is_successful(): is_done UND success=True
        # - final_result(): finaler Text
        try:
            success_flag = result.is_successful()
        except Exception:
            success_flag = None
        try:
            done = result.is_done()
        except Exception:
            done = False
        final = ''
        try:
            final = (result.final_result() or '')[:600]
        except Exception:
            pass

        # is_successful() liefert True | False | None.
        # None heisst: Agent hat done() aufgerufen ohne success-Parameter
        # → behandeln wir als unsicher/needs_manual.
        is_real_success = (success_flag is True)

        # URL aus final extrahieren (oft im Plain-Text)
        backlink_url = ''
        if final:
            import re
            m = re.search(r'https?://[^\s<>"\'\)]+', final)
            if m:
                backlink_url = m.group(0).rstrip('.,;:)')

        return {
            'done': is_real_success,  # nur echte Erfolge -> SUCCESS Status
            'agent_called_done': bool(done),
            'success_flag': success_flag,
            'final': final,
            'backlink_url': backlink_url,
        }

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

    # ---- Takeover/Handback (controlled_by) ---------------------------------

    HUMAN_CONTROL_MAX_S = 30 * 60  # max 30 Min Mensch-Steuerung
    HUMAN_CONTROL_POLL_S = 3

    def _wait_while_human_controls(self):
        """Blockiert solange controlled_by == HUMAN. Beendet sich wenn
        der User per Handback (controlled_by=BOT) die Steuerung zurueckgibt
        ODER 30 Min Timeout erreicht.

        Damit kann der User jederzeit (nicht nur bei NEEDS_MANUAL) eingreifen:
        Takeover-API setzt controlled_by=HUMAN → Bot bleibt vor naechstem Step
        stehen → User klickt im noVNC → User klickt "Steuerung zurueckgeben".
        """
        # Quick-Check: Bot in Control? Dann nichts tun, Step laeuft.
        fresh = SubmissionAttempt.objects.only('controlled_by').get(pk=self.attempt.id)
        if fresh.controlled_by != ControlledBy.HUMAN:
            return
        self._log('User hat Steuerung uebernommen — Bot pausiert', 'warn')
        deadline = time.time() + self.HUMAN_CONTROL_MAX_S
        while time.time() < deadline:
            time.sleep(self.HUMAN_CONTROL_POLL_S)
            fresh = SubmissionAttempt.objects.only('controlled_by', 'status').get(
                pk=self.attempt.id,
            )
            # Wenn Status terminal wurde (User hat Success/Skip gedrueckt),
            # NICHT zum Bot zurueck — outer-Schleife kuemmert sich
            if fresh.status in (
                SubmissionAttemptStatus.SUCCESS,
                SubmissionAttemptStatus.SKIPPED,
                SubmissionAttemptStatus.FAILED_OTHER,
            ):
                self.attempt.refresh_from_db()
                return
            if fresh.controlled_by == ControlledBy.BOT:
                self.attempt.refresh_from_db()
                self._log('User hat Steuerung zurueckgegeben — Bot uebernimmt', 'info')
                return
        self._log('Takeover-Timeout (30 Min) — Bot uebernimmt automatisch', 'warn')
        SubmissionAttempt.objects.filter(pk=self.attempt.id).update(
            controlled_by=ControlledBy.BOT,
        )
        self.attempt.refresh_from_db()

    # ---- Wait-Loop fuer manuellen Eingriff ---------------------------------

    MANUAL_WAIT_MAX_S = 30 * 60      # max 30 Minuten warten
    MANUAL_WAIT_POLL_S = 5            # alle 5 Sekunden DB pollen
    MANUAL_SCREENSHOT_INTERVAL_S = 30  # alle 30s Screenshot fuer Live-Tracking

    def _wait_for_user_intervention(self):
        """Polling-Loop solange Status = NEEDS_MANUAL ist.

        Browser bleibt offen, User kann via noVNC eingreifen. Loop endet wenn:
        - User markiert manuell als SUCCESS (oder anderes Terminal-Status)
        - User skipped → SKIPPED
        - Timeout MANUAL_WAIT_MAX_S → bleibt NEEDS_MANUAL, Browser dann gestoppt
        """
        from ..models import SubmissionAttempt
        deadline = time.time() + self.MANUAL_WAIT_MAX_S
        last_screenshot = 0.0
        self._log(
            f'Bot wartet auf manuellen Eingriff (max {self.MANUAL_WAIT_MAX_S//60} Min). '
            f'Live-View: {BrowserContainerClient.public_novnc_url()}',
            'warn',
        )
        while time.time() < deadline:
            # Status aus DB neu laden — User-Action via API setzt das
            fresh = SubmissionAttempt.objects.only('status').get(pk=self.attempt.id)
            if fresh.status != SubmissionAttemptStatus.NEEDS_MANUAL:
                self._log(f'User-Aktion empfangen: Status -> {fresh.status}', 'info')
                # Sync auf das in-memory-Objekt
                self.attempt.refresh_from_db()
                # Bei Erfolg: Email-Confirm laufen lassen
                if fresh.status == SubmissionAttemptStatus.SUCCESS:
                    self._run_email_verification()
                return
            # Periodisch Screenshot fuer Step-Log/Live-Tracking
            if time.time() - last_screenshot > self.MANUAL_SCREENSHOT_INTERVAL_S:
                last_screenshot = time.time()
                self._capture_screenshot(label='waiting')
            time.sleep(self.MANUAL_WAIT_POLL_S)
        # Timeout — Browser wird im finally gestoppt
        self._log(
            f'Wait-Loop Timeout nach {self.MANUAL_WAIT_MAX_S//60} Min — keine User-Aktion. '
            f'Browser wird gestoppt.',
            'warn',
        )

    # ---- Link-Verifikation -------------------------------------------------

    def _run_link_verification(self, candidate_url: str):
        """Prueft ob auf der Source-Seite ein naturmacher.de-Backlink existiert.

        Setzt Status:
        - SUCCESS wenn gefunden  (mit is_dofollow + final URL)
        - FAILED_NO_LINK wenn nirgends gefunden
        - NEEDS_MANUAL wenn der Verifier komplett crashed (z.B. Site offline)
        """
        from .link_verifier import verify_backlink
        a = self.attempt
        start_urls = []
        if candidate_url:
            start_urls.append(candidate_url)
        # Fallback: Source-Anmelde-URL — manchmal landet der Eintrag direkt dort
        # in einer Listenansicht.
        if self.source.url and self.source.url not in start_urls:
            start_urls.append(self.source.url)
        try:
            result = verify_backlink(start_urls, same_domain_only=True)
        except Exception as exc:
            a.status = SubmissionAttemptStatus.NEEDS_MANUAL
            a.error_message = f'LinkVerifier-Crash: {exc}'
            a.save(update_fields=['status', 'error_message', 'updated_at'])
            self._log(f'LinkVerifier-Fehler: {exc}', 'error')
            return
        if result.found:
            a.status = SubmissionAttemptStatus.SUCCESS
            a.is_verified_live = True
            a.is_dofollow = result.is_dofollow
            a.last_verified_at = timezone.now()
            a.backlink_url = result.public_url
            a.save(update_fields=[
                'status', 'is_verified_live', 'is_dofollow', 'last_verified_at',
                'backlink_url', 'updated_at',
            ])
            label = 'DoFollow ✅' if result.is_dofollow else 'NoFollow'
            self._log(
                f'Backlink VERIFIZIERT auf {result.public_url[:90]} ({label})',
                'info',
            )
        else:
            a.status = SubmissionAttemptStatus.FAILED_NO_LINK
            a.error_message = (
                f'Kein naturmacher.de-Link auf den geprueften Seiten gefunden: '
                f'{", ".join(result.pages_checked[:5])}'
            )
            a.save(update_fields=['status', 'error_message', 'updated_at'])
            self._log(
                f'Kein Backlink auf {len(result.pages_checked)} Seite(n) gefunden — '
                f'Bot dachte er war fertig, aber Link existiert nirgends',
                'warn',
            )

    # ---- Email-Confirmation ------------------------------------------------

    def _run_email_verification(self):
        """Sucht nach Confirm-Mail im IMAP-Postfach des Profils und klickt den Link.

        Wird nach erfolgreicher Submission aufgerufen — viele Verzeichnisse
        schicken eine Bestaetigungs-Mail, die geklickt werden muss damit der
        Eintrag wirklich live geht. Wenn IMAP-Creds fehlen oder keine Mail
        kommt: Skip-Log, kein Hard-Fail (Submission-Status bleibt success).
        """
        if not self.profile.imap_password:
            self._log('Email-Confirm uebersprungen — keine IMAP-Creds im Profil', 'info')
            return
        from .email_verifier import verify_for_domain
        domain = self.source.domain or ''
        if not domain:
            return
        # Kurzer Vorlauf damit die Confirm-Mail ankommen kann
        time.sleep(8)
        self._log(f'Suche Confirm-Mail von {domain}...', 'info')
        try:
            result = verify_for_domain(self.profile, domain, max_wait_s=120, poll_interval_s=5)
        except Exception as exc:
            self._log(f'EmailVerifier-Fehler: {exc}', 'error')
            return
        if result.success:
            self._log(
                f'Email bestaetigt → {result.confirmation_url[:80]} (Mail: "{result.mail_subject[:60]}")',
                'info',
            )
            # backlink_url priorisieren: Confirm-URL ist oft die "active" page
            if not self.attempt.backlink_url:
                self.attempt.backlink_url = result.confirmation_url
                self.attempt.save(update_fields=['backlink_url', 'updated_at'])
        elif result.skipped_reason == 'mail_not_found':
            self._log(f'Keine Confirm-Mail von {domain} gefunden (in 2 min)', 'warn')
        elif result.skipped_reason == 'no_imap_creds':
            self._log('IMAP-Creds fehlen — Email-Confirm skipped', 'info')
        else:
            self._log(f'EmailVerifier-Fehler: {result.error}', 'warn')

    # ---- Captcha-Detection -------------------------------------------------

    def _make_captcha_step_callback(self, browser_session):
        """Erzeugt einen Callback den der browser-use Agent nach jedem Step
        aufruft. Dort pruefen wir:

        1. Steuert der Bot ueberhaupt? (controlled_by) — wenn HUMAN, blockieren
        2. Ist ein Captcha aufgetaucht? — Cascade aufrufen

        Signatur (browser-use 0.12.x): callback(state, model_output, step_index)
        """
        async def _callback(state, model_output, step_index):
            # 1. Wenn User die Steuerung uebernommen hat: warten bis er sie zurueck gibt
            await asyncio.get_event_loop().run_in_executor(
                None, self._wait_while_human_controls,
            )
            # 2. Captcha-Check
            try:
                page = await browser_session.get_current_page()
                detect = await page.evaluate(CAPTCHA_DETECT_JS)
            except Exception as exc:
                logger.debug('captcha-detect skip: %s', exc)
                return
            kind = detect.get('kind', 'none')
            if kind == 'none':
                return
            site_key = detect.get('site_key', '')
            page_url = page.url
            self._log(f'Captcha erkannt: {kind} (site_key={site_key[:20]}...)', 'warn')

            # Cascade aufrufen
            cascade = CaptchaCascade(
                capsolver_key=getattr(self.user, 'capsolver_api_key', '') or '',
                twocaptcha_key=getattr(self.user, 'twocaptcha_api_key', '') or '',
            )
            ctx = CaptchaContext(
                kind=CaptchaKind(kind),
                page_url=page_url,
                site_key=site_key,
                invisible=bool(detect.get('invisible', False)),
                enterprise=bool(detect.get('enterprise', False)),
            )
            sol: CaptchaSolution = await asyncio.get_event_loop().run_in_executor(
                None, cascade.solve, ctx,
            )
            if sol.success and sol.token:
                try:
                    await page.evaluate(CAPTCHA_INJECT_JS, sol.token, kind)
                    self._log(
                        f'Captcha-Token injiziert via {sol.solver_used} ({sol.cost_eur} €)',
                        'info',
                    )
                    self.attempt.captcha_solver_used = sol.solver_used
                    self.attempt.cost_eur = (self.attempt.cost_eur or 0) + sol.cost_eur
                    self.attempt.save(update_fields=[
                        'captcha_solver_used', 'cost_eur', 'updated_at',
                    ])
                except Exception as exc:
                    self._log(f'Token-Injection fehlgeschlagen: {exc}', 'error')
            elif sol.needs_manual:
                self._log('Captcha → manueller Eingriff noetig (Bot pausiert)', 'warn')
                # Status-Update damit User es im Dashboard sieht
                self.attempt.status = SubmissionAttemptStatus.NEEDS_MANUAL
                self.attempt.captcha_solver_used = 'manual'
                self.attempt.save(update_fields=[
                    'status', 'captcha_solver_used', 'updated_at',
                ])
                # Wait-Loop direkt im Callback — User kann Captcha im noVNC selbst loesen.
                # Wir bleiben hier blocked bis User-Action via API kommt.
                await asyncio.get_event_loop().run_in_executor(
                    None, self._wait_for_user_intervention,
                )
                # Nach User-Action: weiter mit Agent-Steps wenn Status zurueck auf RUNNING gesetzt
            else:
                self._log(f'Captcha-Solver {sol.solver_used}: {sol.error}', 'error')
        return _callback


class _BrowserUseUnavailable(RuntimeError):
    """Marker-Exception: browser-use ist nicht installiert oder nicht nutzbar.

    Wird vom Runner abgefangen und als Soft-Fallback behandelt
    (kein Hard-Fail, sondern Foundation-Test ohne echten Submit).
    """

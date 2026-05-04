"""Email-Verifier — sucht und klickt Bestaetigungs-Links.

Workflow:
1. Nach erfolgreicher Site-Registrierung: BotRunner ruft verify_for_domain()
2. Verifier verbindet via IMAP-SSL (Default Zoho)
3. Polling alle 5s, max 120s, sucht ungelesene Mails wo:
   - From enthaelt die Source-Domain (z.B. "lexfinder.de")
   - ODER Subject enthaelt "Bestaetig|Confirm|Verify|Activ"
4. Aus Mail-Body Confirm-Link extrahieren (typische Patterns)
5. Link via httpx ansprechen (GET)
6. Mail als "gesehen" markieren

Dokumentiertes Risiko: nicht 100% — manche Sites
- senden Confirm-Mails von externen Domains (mailgun, sendgrid)
- haben Captcha auf der Confirm-Seite
- nutzen Tokens die im Browser geklickt werden muessen (JS-Action)

Bei Failure: Bot meldet 'manuell bestaetigen' und gibt User die Mail-Subject + Sender.
"""
from __future__ import annotations

import imaplib
import logging
import re
import time
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# Confirm-Link-Patterns: extrahiert URLs die wahrscheinlich Bestaetigungs-Links sind.
# Reihenfolge nach Spezifitaet — spezifische zuerst.
CONFIRM_URL_PATTERNS = [
    # Direkter Verify-Link mit Token
    re.compile(r'https?://[^\s<>"]+(?:confirm|verify|activate|aktivier|bestaetig|validate|opt-?in)[^\s<>"]*', re.IGNORECASE),
    # Token-Patterns (?token=, ?key=, ?activation=)
    re.compile(r'https?://[^\s<>"]+\?(?:token|key|activation|verify|hash|code)=[^\s<>"&]+', re.IGNORECASE),
    # /confirm/<hash>/ Pfade
    re.compile(r'https?://[^\s<>"]+/(?:confirm|verify|activate)/[A-Za-z0-9_\-]+/?', re.IGNORECASE),
]

CONFIRM_SUBJECT_PATTERNS = re.compile(
    r'(bestaetig|confirm|verify|activ|opt-?in|registrierung|welcome|willkommen)',
    re.IGNORECASE,
)


@dataclass
class VerifyResult:
    success: bool = False
    confirmation_url: str = ''
    mail_subject: str = ''
    mail_from: str = ''
    error: str = ''
    skipped_reason: str = ''  # z.B. 'no_imap_creds', 'mail_not_found'


def _decode_header(value: str) -> str:
    if not value:
        return ''
    parts = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(enc or 'utf-8', errors='replace'))
            except Exception:
                parts.append(chunk.decode('utf-8', errors='replace'))
        else:
            parts.append(chunk)
    return ''.join(parts)


def _body_text(msg) -> str:
    """Liefert text/plain ODER text/html Body als String."""
    if msg.is_multipart():
        text = ''
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    text += payload.decode(part.get_content_charset() or 'utf-8',
                                            errors='replace')
        if not text:
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        text += payload.decode(part.get_content_charset() or 'utf-8',
                                                errors='replace')
        return text
    payload = msg.get_payload(decode=True)
    return payload.decode(msg.get_content_charset() or 'utf-8', errors='replace') if payload else ''


def _extract_confirm_url(body: str, domain_hint: str) -> str:
    """Sucht Confirm-Link im Body. Bevorzugt URLs auf der Source-Domain."""
    candidates = []
    for pat in CONFIRM_URL_PATTERNS:
        for m in pat.findall(body):
            candidates.append(m)
    if not candidates:
        return ''
    # Bevorzuge URL die domain_hint enthaelt (z.B. "lexfinder.de")
    for url in candidates:
        if domain_hint and domain_hint.lower() in url.lower():
            return url.rstrip('.,;:)')
    return candidates[0].rstrip('.,;:)')


def verify_for_domain(profile, domain: str, *, max_wait_s: int = 120,
                       poll_interval_s: int = 5) -> VerifyResult:
    """Sucht in der IMAP-Inbox nach Confirm-Mail von ``domain`` und klickt den Link.

    Args:
        profile: NaturmacherProfile (mit imap_* Feldern)
        domain: Source-Domain z.B. ``"lexfinder.de"``
        max_wait_s: max. Polling-Dauer
        poll_interval_s: Zeit zwischen Inbox-Checks

    Returns:
        VerifyResult mit success + confirmation_url falls erfolgreich
    """
    host = profile.imap_host or 'imappro.zoho.eu'
    port = profile.imap_port or 993
    user = profile.imap_username or profile.email
    pw = profile.imap_password
    if not (host and user and pw):
        return VerifyResult(skipped_reason='no_imap_creds',
                             error='IMAP-Creds fehlen im Profil')

    deadline = time.time() + max_wait_s
    try:
        M = imaplib.IMAP4_SSL(host, port)
        M.login(user, pw)
    except Exception as exc:
        return VerifyResult(error=f'IMAP-Login: {exc}')

    try:
        M.select('INBOX')
        seen_uids = set()
        domain_lower = domain.lower()
        while time.time() < deadline:
            status, data = M.search(None, '(UNSEEN)')
            if status != 'OK':
                time.sleep(poll_interval_s)
                continue
            for uid in (data[0] or b'').split():
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)
                status, msg_data = M.fetch(uid, '(RFC822)')
                if status != 'OK':
                    continue
                msg = message_from_bytes(msg_data[0][1])
                subject = _decode_header(msg.get('Subject', ''))
                sender_raw = msg.get('From', '')
                sender_name, sender_email = parseaddr(sender_raw)

                # Match: Domain in From-Adresse ODER Confirm-Subject + Plausibilitaet
                from_match = domain_lower in sender_email.lower()
                subj_match = bool(CONFIRM_SUBJECT_PATTERNS.search(subject))
                if not (from_match or subj_match):
                    continue
                body = _body_text(msg)
                if domain_lower not in body.lower() and not from_match:
                    # Subject sah passend aus, aber kein Bezug zur Domain
                    continue

                confirm_url = _extract_confirm_url(body, domain_lower)
                if not confirm_url:
                    logger.info('Mail "%s" hat keine Confirm-URL', subject[:60])
                    continue

                # Klick die URL
                try:
                    r = httpx.get(confirm_url, follow_redirects=True, timeout=20)
                    success = 200 <= r.status_code < 400
                except Exception as exc:
                    return VerifyResult(error=f'Confirm-URL nicht ladbar: {exc}',
                                         confirmation_url=confirm_url,
                                         mail_subject=subject, mail_from=sender_email)

                # Mark als gelesen
                try:
                    M.store(uid, '+FLAGS', '\\Seen')
                except Exception:
                    pass

                return VerifyResult(
                    success=success,
                    confirmation_url=confirm_url,
                    mail_subject=subject,
                    mail_from=sender_email,
                    error='' if success else f'HTTP {r.status_code}',
                )

            time.sleep(poll_interval_s)
        return VerifyResult(skipped_reason='mail_not_found',
                             error=f'Keine Mail von {domain} innerhalb {max_wait_s}s gefunden')
    finally:
        try:
            M.logout()
        except Exception:
            pass

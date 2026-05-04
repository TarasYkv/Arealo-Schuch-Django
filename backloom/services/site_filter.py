"""Site-Filter — heuristische Pre-Submission-Pruefung.

Bevor wir den teuren Browser-Bot starten, machen wir einen schnellen HTTP-
Check ob die URL ueberhaupt eine Submission-faehige Webseite ist:

- Parked Domain Detection (z.B. firma-eintragen-regional.de zeigte Sedo-Page)
- Soft-404 / leere Seiten
- Article-only-Seiten ohne Form (z.B. lexicanum.de listet andere Verzeichnisse,
  ist selbst keine)
- Login-walled Seiten ohne oeffentliches Eintragsformular

Liefert SiteFilterResult mit {is_submittable, reason, evidence}.
Im BotRunner: wenn is_submittable=False → Status FAILED_OTHER + Source als
is_rejected markieren, kein Container-Spawn.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)

# Domain-Patterns die typische Parked-/Sale-Pages dranhaengen
PARKED_DOMAIN_HINTS = [
    'sedoparking.com', 'bodis.com', 'parkingcrew.net',
    'cashparking.com', 'this-domain-for-sale', 'domain-for-sale',
    'domain.com/lander', 'parking-domain', 'godaddy.com/lander',
]

# Stark indikative Strings im Body fuer "ist parked/dropshipping/sales-page"
PARKED_BODY_HINTS = [
    'this domain is for sale',
    'diese domain steht zum verkauf',
    'inquire about this domain',
    'parked at',
    'this page is parked',
    'sponsored listings',
]

# Stark indikative Strings die auf "echte Submission-Site" hindeuten
SUBMISSION_BODY_HINTS = [
    'firma eintragen', 'eintrag erstellen', 'unternehmen eintragen',
    'kostenlos eintragen', 'kostenloser eintrag', 'jetzt eintragen',
    'registrieren', 'anmelden', 'sign up', 'sign-up', 'create account',
    'register now', 'submit your business', 'add your business',
    'add listing', 'add company', 'firmeneintrag', 'unternehmenseintrag',
    'profil erstellen', 'jetzt anmelden', 'neuer eintrag',
]


@dataclass
class SiteFilterResult:
    is_submittable: bool
    reason: str = ''                 # Slug fuer Logging
    evidence: str = ''               # Klartext-Begruendung
    page_size_bytes: int = 0
    final_url: str = ''


def check_submission_site(url: str, timeout_s: int = 10) -> SiteFilterResult:
    """Pre-Submission-Pruefung. Wenig Daten ueber HTTPS, schnell."""
    if not url:
        return SiteFilterResult(False, 'no_url', 'Keine URL angegeben')

    try:
        with httpx.Client(headers={'User-Agent': USER_AGENT, 'Accept-Language': 'de-DE,de;q=0.9'},
                           follow_redirects=True, timeout=timeout_s) as c:
            r = c.get(url)
    except httpx.TimeoutException:
        return SiteFilterResult(False, 'timeout', f'HTTP-Timeout nach {timeout_s}s')
    except Exception as exc:
        return SiteFilterResult(False, 'http_error', f'HTTP-Fehler: {exc}')

    final_url = str(r.url)
    body = r.text or ''
    body_lower = body.lower()
    size = len(body.encode('utf-8', errors='replace'))

    # 1. HTTP-Status
    if r.status_code >= 400:
        return SiteFilterResult(False, 'http_status',
                                  f'Status {r.status_code} — Site liefert Fehler',
                                  page_size_bytes=size, final_url=final_url)

    # 2. Parked Domain — Redirect-Ziel oder Body
    if any(h in final_url.lower() for h in PARKED_DOMAIN_HINTS):
        return SiteFilterResult(False, 'parked_domain',
                                  f'Redirect zu Parking-Domain: {final_url[:80]}',
                                  page_size_bytes=size, final_url=final_url)
    for hint in PARKED_BODY_HINTS:
        if hint in body_lower:
            return SiteFilterResult(False, 'parked_domain',
                                      f'Body enthaelt Parking-Hint: "{hint}"',
                                      page_size_bytes=size, final_url=final_url)

    # 3. Zu wenig Inhalt — Soft-404 oder leerer Site
    if size < 500:
        return SiteFilterResult(False, 'too_small',
                                  f'Body nur {size} Bytes — leere oder Soft-404-Seite',
                                  page_size_bytes=size, final_url=final_url)

    # 4. Article-only Detection — Site ist Magazin/Blog ohne Submission
    has_submission_hint = any(h in body_lower for h in SUBMISSION_BODY_HINTS)
    has_form = bool(re.search(r'<form[^>]*>', body, re.IGNORECASE))
    if not has_submission_hint and not has_form:
        # Wenn die Page weder ein Form hat noch Sign-Up-Vokabular,
        # ist sie wahrscheinlich nur Information.
        return SiteFilterResult(False, 'no_form',
                                  'Keine <form> + keine Sign-Up-Begriffe — Article-Page?',
                                  page_size_bytes=size, final_url=final_url)

    # 5. Lexicanum-Pattern: viele externe Links, wenig eigener Form-Inhalt
    # — wenn die Page mehr als 50 externe Links hat und keine eigene Submission,
    # ist es eine Verzeichnis-Liste (article-only)
    external_link_count = len(re.findall(r'<a\s+[^>]*href=["\']https?://[^"\']+["\']',
                                           body, re.IGNORECASE))
    if external_link_count > 50 and not has_form:
        return SiteFilterResult(False, 'directory_listing',
                                  f'{external_link_count} externe Links + kein <form> — Article '
                                  f'die andere Verzeichnisse listet?',
                                  page_size_bytes=size, final_url=final_url)

    # Default: probably submittable
    return SiteFilterResult(True, 'ok',
                              f'Form-Hint gefunden, {size} Bytes, {external_link_count} ext. Links',
                              page_size_bytes=size, final_url=final_url)

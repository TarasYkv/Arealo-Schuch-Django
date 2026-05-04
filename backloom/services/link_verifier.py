"""LinkVerifier — prueft ob auf der Ziel-Site wirklich ein naturmacher.de-Backlink existiert.

Das ist der EINZIG ehrliche Erfolgs-Check fuer eine Backlink-Submission:
nicht "der Bot hat done() gerufen", sondern "es gibt tatsaechlich einen
<a href*='naturmacher.de'> auf einer oeffentlich erreichbaren Seite der Source".

Algorithmus:
1. Start-URLs sammeln:
   - Die backlink_url aus dem Attempt (oft "/mein-konto" oder "/profile/123")
   - Die Source-Origin-URL als Fallback ("https://example.com/firma-eintragen")
2. Pro Start-URL:
   - HTML laden (httpx mit normalem User-Agent)
   - <a href*="naturmacher.de"> suchen
3. Wenn nicht direkt gefunden, "View public profile"-Links suchen und
   bis zu 2 Hops folgen (Begriffe: "profil ansehen", "view profile",
   "öffentliches profil", "vorschau", "preview", "ansehen", "zur firma")
4. Ergebnis: gefunden + URL + is_dofollow + welche Page

Sicher gegen:
- Login-walled-Seiten (kein Login-Cookie → 200 mit "Bitte einloggen")
  Resultat: kein Link gefunden → FAILED_NO_LINK
- JavaScript-only-rendered Listen (BS findet nichts → FAILED_NO_LINK)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

TARGET_DOMAIN = 'naturmacher.de'
USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)
TIMEOUT_S = 15
MAX_HOPS = 2  # max Tiefe beim Folgen von "Public Profile"-Links

# Regex-Patterns die auf "view profile"-Buttons hinweisen
PUBLIC_PROFILE_TEXTS = re.compile(
    r'(profil\s*ansehen|oeffentliches?\s*profil|öffentliches?\s*profil|'
    r'view\s*(?:public\s*)?profile|vorschau|preview|ansehen|'
    r'zur\s*firmen?seite|firma\s*ansehen|eintrag\s*ansehen|'
    r'mein\s*eintrag|public\s*page)',
    re.IGNORECASE,
)


@dataclass
class LinkVerifyResult:
    found: bool = False
    public_url: str = ''         # die Seite auf der der Link gefunden wurde
    link_url: str = ''           # der genaue href-Wert der gefunden wurde
    is_dofollow: bool | None = None
    pages_checked: list[str] = field(default_factory=list)
    error: str = ''


def _extract_target_links(html: str) -> list[tuple[str, bool]]:
    """Findet alle <a href> die auf naturmacher.de zeigen.
    Liefert Liste von (href, is_dofollow).
    """
    if not html:
        return []
    out = []
    pattern = re.compile(
        r'<a\s+([^>]*?)href=["\']([^"\']*?naturmacher\.de[^"\']*?)["\']([^>]*)>',
        re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        attrs_before, href, attrs_after = m.group(1), m.group(2), m.group(3)
        full_attrs = (attrs_before + ' ' + attrs_after).lower()
        # rel kann sein: nofollow, ugc, sponsored — alles "no-link-juice"
        is_nofollow = bool(re.search(r'rel\s*=\s*["\'][^"\']*?(nofollow|ugc|sponsored)',
                                      full_attrs))
        out.append((href, not is_nofollow))
    return out


def _extract_profile_links(html: str, base_url: str) -> list[str]:
    """Findet 'View public profile'-Style Links."""
    if not html:
        return []
    candidates = []
    # <a> mit verdaechtigem Text
    a_pattern = re.compile(r'<a\s+([^>]*?)>([^<]+)</a>', re.IGNORECASE | re.DOTALL)
    for m in a_pattern.finditer(html):
        attrs, text = m.group(1), m.group(2)
        if PUBLIC_PROFILE_TEXTS.search(text):
            href_m = re.search(r'href=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if href_m:
                candidates.append(urljoin(base_url, href_m.group(1)))
    return list(dict.fromkeys(candidates))  # dedupe order-preserving


def _fetch(url: str) -> tuple[str, str]:
    """Liefert (final_url, html_text). Bei Fehler ('', '')."""
    try:
        with httpx.Client(headers={'User-Agent': USER_AGENT},
                            follow_redirects=True, timeout=TIMEOUT_S) as c:
            r = c.get(url)
            if r.status_code >= 400:
                return ('', '')
            return (str(r.url), r.text)
    except Exception as exc:
        logger.warning('fetch %s: %s', url, exc)
        return ('', '')


def verify_backlink(start_urls: Iterable[str],
                     same_domain_only: bool = True) -> LinkVerifyResult:
    """Sucht in den uebergebenen URLs (+ "view profile"-Links 1-2 Hops tief)
    nach einem <a href*='naturmacher.de'>.

    Args:
        start_urls: URLs zum Start (z.B. backlink_url + source.url)
        same_domain_only: nur Profil-Links auf derselben Source-Domain folgen
                          (verhindert dass wir z.B. social-share-Links folgen)

    Returns:
        LinkVerifyResult
    """
    visited = set()
    res = LinkVerifyResult()
    queue: list[tuple[str, int]] = []
    for u in start_urls:
        if u and u not in visited:
            queue.append((u, 0))
            visited.add(u)

    domains = set()
    for u in start_urls:
        if u:
            try:
                domains.add(urlparse(u).netloc)
            except Exception:
                pass

    while queue:
        url, depth = queue.pop(0)
        final_url, html = _fetch(url)
        if not html:
            continue
        res.pages_checked.append(final_url or url)

        # Direkter Match?
        target_links = _extract_target_links(html)
        if target_links:
            link_url, is_df = target_links[0]
            res.found = True
            res.public_url = final_url or url
            res.link_url = link_url
            res.is_dofollow = is_df
            return res

        # Wenn nicht gefunden: Profil-Links sammeln und (bis MAX_HOPS) folgen
        if depth >= MAX_HOPS:
            continue
        for next_url in _extract_profile_links(html, final_url or url):
            if next_url in visited:
                continue
            if same_domain_only:
                try:
                    if urlparse(next_url).netloc not in domains:
                        continue
                except Exception:
                    continue
            visited.add(next_url)
            queue.append((next_url, depth + 1))

    return res

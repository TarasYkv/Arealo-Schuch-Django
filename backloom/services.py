"""
BackLoom Scraping Engine
Durchsucht Suchmaschinen und Plattformen nach Backlink-Möglichkeiten
"""

import logging
import random
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import connection
from django.utils import timezone

# YouTube Untertitel
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False

from .models import (
    BacklinkCategory,
    BacklinkSearch,
    BacklinkSource,
    SearchQuery,
    SourceType,
)

logger = logging.getLogger(__name__)


def sanitize_for_mysql(text: str) -> str:
    """Entfernt Emojis und andere 4-Byte UTF-8 Zeichen für MySQL utf8 Kompatibilität."""
    if not text:
        return text
    # Entferne alle Zeichen außerhalb des BMP (Basic Multilingual Plane)
    # Das sind alle Zeichen mit Codepoint > 0xFFFF (4-Byte UTF-8)
    return ''.join(c for c in text if ord(c) <= 0xFFFF)


# User-Agents für Rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# Domains die ausgeschlossen werden sollen
EXCLUDED_DOMAINS = [
    'google.com', 'google.de', 'bing.com', 'yahoo.com', 'duckduckgo.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'amazon.com', 'amazon.de', 'ebay.de', 'ebay.com',
    'wikipedia.org', 'pinterest.com', 'tiktok.com',
    # Spam/Low-Quality
    'blogspot.com', 'wordpress.com', 'tumblr.com', 'weebly.com',
]


class SourceHealthCheck:
    """Health-Check für Suchmaschinen-Quellen"""

    # Aktive Quellen (funktionieren zuverlässig)
    SOURCES = {
        'duckduckgo': {
            'name': 'DuckDuckGo',
            'test_url': 'https://html.duckduckgo.com/html/?q=test',
            'check_text': 'duckduckgo',
            'enabled': True,
        },
        'youtube': {
            'name': 'YouTube API',
            'test_url': 'https://www.googleapis.com/youtube/v3/search',
            'check_text': None,  # API check
            'is_api': True,
            'enabled': True,
        },
        'tiktok': {
            'name': 'TikTok (Brave + Supadata)',
            'test_url': 'https://api.search.brave.com/res/v1/web/search',
            'check_text': None,  # API check
            'is_api': True,
            'enabled': True,
        },
        'brave': {
            'name': 'Brave Search API',
            'test_url': 'https://api.search.brave.com/res/v1/web/search',
            'check_text': None,  # API check
            'is_api': True,
            'enabled': True,
        },
    }

    # Deaktivierte Quellen (blockiert oder benötigen JavaScript)
    DISABLED_SOURCES = {
        'google': {
            'name': 'Google',
            'reason': 'Benötigt JavaScript',
            'enabled': False,
        },
        'bing': {
            'name': 'Bing',
            'reason': 'Benötigt JavaScript',
            'enabled': False,
        },
        'ecosia': {
            'name': 'Ecosia',
            'reason': 'Benötigt JavaScript',
            'enabled': False,
        },
        'reddit': {
            'name': 'Reddit',
            'reason': 'Blockiert (403)',
            'enabled': False,
        },
    }

    @classmethod
    def check_source(cls, source_key: str, user=None) -> Dict:
        """Prüft eine einzelne Quelle"""
        # Prüfen ob deaktivierte Quelle
        if source_key in cls.DISABLED_SOURCES:
            disabled = cls.DISABLED_SOURCES[source_key]
            return {
                'key': source_key,
                'name': disabled['name'],
                'status': 'disabled',
                'message': disabled['reason'],
                'response_time': 0,
                'enabled': False,
            }

        source = cls.SOURCES.get(source_key)
        if not source:
            return {'status': 'error', 'message': 'Unbekannte Quelle'}

        result = {
            'key': source_key,
            'name': source['name'],
            'status': 'unknown',
            'message': '',
            'response_time': 0,
            'enabled': True,
        }

        try:
            start_time = time.time()

            # YouTube API spezielle Behandlung
            if source.get('is_api') and source_key == 'youtube':
                api_key = None
                if user:
                    api_key = getattr(user, 'youtube_api_key', None)
                if not api_key:
                    result['status'] = 'warning'
                    result['message'] = 'API-Key nicht konfiguriert'
                    return result

                response = requests.get(
                    source['test_url'],
                    params={'part': 'snippet', 'q': 'test', 'type': 'video', 'maxResults': 1, 'key': api_key},
                    timeout=10
                )
                result['response_time'] = round((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    result['status'] = 'ok'
                    result['message'] = 'API funktioniert'
                elif response.status_code == 403:
                    result['status'] = 'error'
                    result['message'] = 'API-Key ungültig oder Quota überschritten'
                else:
                    result['status'] = 'error'
                    result['message'] = f'HTTP {response.status_code}'
                return result

            # TikTok: Benötigt Brave + Supadata API Keys
            if source.get('is_api') and source_key == 'tiktok':
                brave_key = None
                supadata_key = None
                if user:
                    brave_key = getattr(user, 'brave_api_key', None)
                    supadata_key = getattr(user, 'supadata_api_key', None)
                
                missing_keys = []
                if not brave_key:
                    missing_keys.append('Brave Search')
                if not supadata_key:
                    missing_keys.append('Supadata')
                
                if missing_keys:
                    result['status'] = 'warning'
                    result['message'] = f'API-Key(s) nicht konfiguriert: {", ".join(missing_keys)}'
                    return result

                # Test Brave Search API
                response = requests.get(
                    'https://api.search.brave.com/res/v1/web/search',
                    params={'q': 'test', 'count': 1},
                    headers={'X-Subscription-Token': brave_key, 'Accept': 'application/json'},
                    timeout=10
                )
                result['response_time'] = round((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    result['status'] = 'ok'
                    result['message'] = 'Brave + Supadata konfiguriert'
                elif response.status_code == 401:
                    result['status'] = 'error'
                    result['message'] = 'Brave API-Key ungültig'
                elif response.status_code == 429:
                    result['status'] = 'warning'
                    result['message'] = 'Brave Rate-Limit erreicht'
                else:
                    result['status'] = 'error'
                    result['message'] = f'Brave HTTP {response.status_code}'
                return result

            # Brave Search API spezielle Behandlung
            if source.get('is_api') and source_key == 'brave':
                api_key = None
                if user:
                    api_key = getattr(user, 'brave_api_key', None)
                if not api_key:
                    result['status'] = 'warning'
                    result['message'] = 'API-Key nicht konfiguriert'
                    return result

                response = requests.get(
                    source['test_url'],
                    params={'q': 'test', 'count': 1},
                    headers={'X-Subscription-Token': api_key, 'Accept': 'application/json'},
                    timeout=10
                )
                result['response_time'] = round((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    result['status'] = 'ok'
                    result['message'] = 'API funktioniert'
                elif response.status_code == 401:
                    result['status'] = 'error'
                    result['message'] = 'API-Key ungültig'
                elif response.status_code == 429:
                    result['status'] = 'warning'
                    result['message'] = 'Rate-Limit erreicht (2000/Monat Free)'
                else:
                    result['status'] = 'error'
                    result['message'] = f'HTTP {response.status_code}'
                return result

            # Standard Scraping-Check
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            }

            response = requests.get(
                source['test_url'],
                headers=headers,
                timeout=15,
                allow_redirects=True
            )
            result['response_time'] = round((time.time() - start_time) * 1000)

            if response.status_code == 200:
                # Prüfen ob erwarteter Content vorhanden
                content_lower = response.text.lower()
                if source['check_text'] and source['check_text'] in content_lower:
                    result['status'] = 'ok'
                    result['message'] = f'Erreichbar ({result["response_time"]}ms)'
                else:
                    result['status'] = 'warning'
                    result['message'] = 'Erreichbar, aber Content ungewöhnlich'
            elif response.status_code == 429:
                result['status'] = 'warning'
                result['message'] = 'Rate-Limit erreicht'
            elif response.status_code == 403:
                result['status'] = 'error'
                result['message'] = 'Zugriff blockiert (403)'
            else:
                result['status'] = 'error'
                result['message'] = f'HTTP {response.status_code}'

        except requests.Timeout:
            result['status'] = 'error'
            result['message'] = 'Timeout'
        except requests.ConnectionError:
            result['status'] = 'error'
            result['message'] = 'Verbindungsfehler'
        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)[:50]

        return result

    @classmethod
    def check_all_sources(cls, user=None) -> List[Dict]:
        """Prüft alle Quellen (aktive + deaktivierte)"""
        results = []
        # Aktive Quellen zuerst
        for source_key in cls.SOURCES.keys():
            results.append(cls.check_source(source_key, user))
        # Dann deaktivierte Quellen
        for source_key in cls.DISABLED_SOURCES.keys():
            results.append(cls.check_source(source_key, user))
        return results


class BacklinkScraper:
    """Haupt-Scraper-Klasse für Backlink-Recherche"""

    def __init__(self, search: BacklinkSearch):
        self.search = search
        self.session = requests.Session()
        self.results: List[Dict] = []
        self.stats = {
            'found': 0,
            'new': 0,
            'updated': 0,
            'errors': 0
        }
        self.source_stats = {
            'google': {'found': 0, 'status': 'pending'},
            'bing': {'found': 0, 'status': 'pending'},
            'duckduckgo': {'found': 0, 'status': 'pending'},
            'ecosia': {'found': 0, 'status': 'pending'},
            'reddit': {'found': 0, 'status': 'pending'},
            'youtube': {'found': 0, 'status': 'pending'},
            'tiktok': {'found': 0, 'status': 'pending'},
        }

    def _get_headers(self) -> Dict[str, str]:
        """Generiert zufällige Headers"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def _delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Zufällige Verzögerung zwischen Requests"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _is_valid_url(self, url: str) -> bool:
        """Prüft ob URL gültig und nicht ausgeschlossen ist"""
        if not url or not url.startswith(('http://', 'https://')):
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')

        # Ausgeschlossene Domains prüfen
        for excluded in EXCLUDED_DOMAINS:
            if excluded in domain:
                return False

        return True

    def _extract_domain(self, url: str) -> str:
        """Extrahiert Domain aus URL"""
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')

    def _clean_text(self, text: str) -> str:
        """Bereinigt Text von HTML und Whitespace"""
        if not text:
            return ''
        # HTML-Entities dekodieren und Whitespace normalisieren
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:500]  # Maximal 500 Zeichen

    def _extract_urls_from_text(self, text: str) -> List[str]:
        """
        Extrahiert URLs aus Text (z.B. YouTube-Beschreibungen)
        Filtert Plattform-URLs (YouTube, Reddit, Social Media) aus
        """
        if not text:
            return []

        # URL-Pattern
        url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;:!?]'
        found_urls = re.findall(url_pattern, text)

        # Bereinigen und filtern
        valid_urls = []
        for url in found_urls:
            # Trailing-Zeichen entfernen
            url = url.rstrip('.,;:!?)')

            if not self._is_valid_url(url):
                continue

            # Zusätzliche Plattform-Filter für extrahierte URLs
            domain = self._extract_domain(url).lower()
            skip_domains = [
                'youtube.com', 'youtu.be', 'reddit.com', 'twitter.com', 'x.com',
                'facebook.com', 'instagram.com', 'tiktok.com', 'linkedin.com',
                'bit.ly', 'goo.gl', 't.co', 'amzn.to',  # Shortlinks
            ]
            if any(skip in domain for skip in skip_domains):
                continue

            valid_urls.append(url)

        return list(set(valid_urls))  # Duplikate entfernen

    def _extract_domains_from_text(self, text: str) -> List[str]:
        """
        Extrahiert Domain-Erwähnungen aus Text (z.B. Untertitel).
        Findet Patterns wie "example.com", "website.de", "forum.org"
        auch wenn kein http:// davor steht.
        """
        if not text:
            return []

        # Domain-Pattern: word.tld (gängige TLDs)
        tlds = r'(?:com|de|org|net|eu|at|ch|io|co|info|biz)'
        domain_pattern = rf'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.{tlds})\b'

        found_domains = re.findall(domain_pattern, text.lower())

        # Filtern
        valid_domains = []
        skip_domains = [
            'youtube.com', 'youtu.be', 'reddit.com', 'twitter.com', 'x.com',
            'facebook.com', 'instagram.com', 'tiktok.com', 'linkedin.com',
            'google.com', 'google.de', 'bit.ly', 'goo.gl', 't.co',
            'amazon.com', 'amazon.de', 'ebay.de', 'ebay.com',
            'paypal.com', 'patreon.com', 'ko-fi.com',  # Bezahl-Plattformen
        ]

        for domain in found_domains:
            domain = domain.lower().strip()
            if len(domain) < 5:  # Zu kurz
                continue
            if any(skip in domain for skip in skip_domains):
                continue
            valid_domains.append(domain)

        return list(set(valid_domains))

    def _get_youtube_transcript(self, video_id: str) -> Optional[str]:
        """
        Holt Untertitel eines YouTube-Videos.
        Versucht: Deutsch manuell → Deutsch auto → Englisch → Erste verfügbare
        """
        if not YOUTUBE_TRANSCRIPT_AVAILABLE:
            return None

        try:
            # Verfügbare Transkripte holen
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            transcript = None

            # Priorität: Deutsch manuell → Deutsch auto → Englisch → Erste
            try:
                transcript = transcript_list.find_transcript(['de'])
            except:
                try:
                    transcript = transcript_list.find_generated_transcript(['de'])
                except:
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                    except:
                        try:
                            # Erste verfügbare
                            for t in transcript_list:
                                transcript = t
                                break
                        except:
                            pass

            if transcript:
                # Text zusammenfügen
                data = transcript.fetch()
                full_text = ' '.join([entry['text'] for entry in data])
                return full_text

        except (TranscriptsDisabled, NoTranscriptFound):
            pass
        except Exception as e:
            logger.debug(f"Transcript error for {video_id}: {e}")

        return None

    def _get_tiktok_transcript(self, video_url: str) -> Optional[str]:
        """
        Holt Untertitel eines TikTok-Videos über die Supadata API.
        Benötigt einen gültigen Supadata API-Key.
        """
        # API Key vom User holen
        api_key = None
        if self.search.triggered_by:
            api_key = getattr(self.search.triggered_by, 'supadata_api_key', None)

        if not api_key:
            self.search.log_progress("  → Supadata: Kein API-Key")
            return None

        video_id = video_url.split('/video/')[-1].split('?')[0][:12] if '/video/' in video_url else video_url[-20:]

        try:
            response = self.session.get(
                'https://api.supadata.ai/v1/transcript',
                params={'url': video_url},
                headers={'x-api-key': api_key},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                # Supadata gibt 'content' als Array mit {text, offset, duration}
                content = data.get('content', [])
                if content:
                    # Text zusammenfügen
                    full_text = ' '.join([seg.get('text', '') for seg in content])
                    self.search.log_progress(f"  → {video_id}: Transkript OK ({len(full_text)} Zeichen)")
                    return full_text
                else:
                    # Response OK aber kein Content - zeige was wir bekommen haben
                    self.search.log_progress(f"  → {video_id}: Kein Content (Keys: {list(data.keys())})")
            elif response.status_code == 404:
                self.search.log_progress(f"  → {video_id}: Keine Untertitel verfügbar (404)")
            elif response.status_code == 401:
                self.search.log_progress(f"  → {video_id}: API-Key ungültig (401)")
            elif response.status_code == 429:
                self.search.log_progress(f"  → {video_id}: Rate-Limit erreicht (429)")
            else:
                self.search.log_progress(f"  → {video_id}: HTTP {response.status_code}")

        except Exception as e:
            self.search.log_progress(f"  → {video_id}: Fehler - {str(e)[:50]}")

        return None

    def _get_tiktok_metadata(self, video_url: str) -> Optional[Dict]:
        """
        Holt Metadaten eines TikTok-Videos über die Supadata Metadata API.
        Gibt Description, Creator-Username und andere Infos zurück.
        """
        api_key = None
        if self.search.triggered_by:
            api_key = getattr(self.search.triggered_by, 'supadata_api_key', None)

        if not api_key:
            return None

        video_id = video_url.split('/video/')[-1].split('?')[0][:12] if '/video/' in video_url else video_url[-20:]

        try:
            response = self.session.get(
                'https://api.supadata.ai/v1/metadata',
                params={'url': video_url},
                headers={'x-api-key': api_key},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                description = data.get('description', '') or ''
                author = data.get('author', {})
                username = author.get('username', '')
                
                if description or username:
                    self.search.log_progress(f"  → {video_id}: Metadata OK (@{username}, {len(description)} Zeichen Desc)")
                    return {
                        'description': description,
                        'username': username,
                        'display_name': author.get('displayName', ''),
                        'title': data.get('title', ''),
                    }
                else:
                    self.search.log_progress(f"  → {video_id}: Metadata leer")
            elif response.status_code == 404:
                self.search.log_progress(f"  → {video_id}: Metadata nicht gefunden (404)")
            else:
                self.search.log_progress(f"  → {video_id}: Metadata HTTP {response.status_code}")

        except Exception as e:
            self.search.log_progress(f"  → {video_id}: Metadata Fehler - {str(e)[:50]}")

        return None

    # ==================
    # GOOGLE SCRAPING
    # ==================
    def search_google(self, query: str, num_results: int = 30) -> List[Dict]:
        """
        Durchsucht Google nach dem Suchbegriff
        Verwendet Google Search mit deutschen Ergebnissen
        """
        results = []
        self.search.log_progress(f"Google-Suche: '{query}'")

        try:
            # Google-Suche URL (deutsche Ergebnisse)
            url = f"https://www.google.de/search?q={quote_plus(query)}&num={num_results}&hl=de&gl=de"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                self.search.log_progress(f"Google: HTTP {response.status_code}")
                self.source_stats['google']['status'] = 'error'
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Mehrere Selektoren versuchen (Google ändert HTML häufig)
            selectors = [
                'div.g',  # Standard
                'div[data-sokoban-container]',  # Neueres Format
                'div.tF2Cxc',  # Alternatives Format
                'div.yuRUbf',  # Link-Container
            ]

            found_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    found_containers = containers
                    self.search.log_progress(f"Google: Verwende Selector '{selector}' ({len(containers)} Container)")
                    break

            if not found_containers:
                # Fallback: Alle Links mit bestimmten Eigenschaften
                self.search.log_progress("Google: Kein Standard-Selector gefunden, versuche Fallback")
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if href.startswith('/url?q='):
                        # Google-Weiterleitungs-Link
                        actual_url = href.split('/url?q=')[1].split('&')[0]
                        if self._is_valid_url(actual_url):
                            title = self._clean_text(link.get_text()) or actual_url
                            results.append({
                                'url': actual_url,
                                'title': title,
                                'description': '',
                                'source_type': SourceType.GOOGLE
                            })
                            if len(results) >= num_results:
                                break
            else:
                # Suchergebnisse parsen
                for result in found_containers:
                    try:
                        # Link finden (verschiedene Möglichkeiten)
                        link_elem = result.select_one('a[href^="http"]') or result.select_one('a[href]')
                        if not link_elem:
                            continue

                        url = link_elem.get('href', '')

                        # Google-Weiterleitungs-Links bereinigen
                        if url.startswith('/url?q='):
                            url = url.split('/url?q=')[1].split('&')[0]

                        if not self._is_valid_url(url):
                            continue

                        # Titel finden
                        title_elem = result.select_one('h3') or result.select_one('h2')
                        title = self._clean_text(title_elem.get_text()) if title_elem else ''

                        # Beschreibung finden
                        desc_selectors = ['div[data-sncf]', 'div.VwiC3b', 'span.aCOpRe', 'div.IsZvec']
                        description = ''
                        for desc_sel in desc_selectors:
                            desc_elem = result.select_one(desc_sel)
                            if desc_elem:
                                description = self._clean_text(desc_elem.get_text())
                                break

                        results.append({
                            'url': url,
                            'title': title,
                            'description': description,
                            'source_type': SourceType.GOOGLE
                        })

                    except Exception as e:
                        logger.debug(f"Error parsing Google result: {e}")
                        continue

            self.source_stats['google']['found'] = len(results)
            self.source_stats['google']['status'] = 'ok' if results else 'warning'
            self.search.log_progress(f"Google: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Google search error: {e}")
            self.search.log_progress(f"Google-Fehler: {e}")
            self.source_stats['google']['status'] = 'error'

        return results

    # ==================
    # BING SCRAPING
    # ==================
    def search_bing(self, query: str, num_results: int = 30) -> List[Dict]:
        """
        Durchsucht Bing nach dem Suchbegriff
        """
        results = []
        self.search.log_progress(f"Bing-Suche: '{query}'")

        try:
            # Bing-Suche URL
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num_results}&setlang=de&cc=de"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                self.search.log_progress(f"Bing: HTTP {response.status_code}")
                self.source_stats['bing']['status'] = 'error'
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Mehrere Selektoren versuchen
            selectors = [
                'li.b_algo',  # Standard
                'div.b_algo',  # Alternatives Format
                'ol#b_results li',  # Container-Format
            ]

            found_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    found_containers = containers
                    self.search.log_progress(f"Bing: Verwende Selector '{selector}' ({len(containers)} Container)")
                    break

            for result in found_containers:
                try:
                    # Link finden
                    link_elem = result.select_one('h2 a') or result.select_one('a[href^="http"]')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    # Beschreibung finden
                    desc_elem = result.select_one('div.b_caption p') or result.select_one('p')
                    description = self._clean_text(desc_elem.get_text()) if desc_elem else ''

                    results.append({
                        'url': url,
                        'title': title,
                        'description': description,
                        'source_type': SourceType.BING
                    })

                except Exception as e:
                    logger.debug(f"Error parsing Bing result: {e}")
                    continue

            self.source_stats['bing']['found'] = len(results)
            self.source_stats['bing']['status'] = 'ok' if results else 'warning'
            self.search.log_progress(f"Bing: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Bing search error: {e}")
            self.search.log_progress(f"Bing-Fehler: {e}")
            self.source_stats['bing']['status'] = 'error'

        return results

    # ==================
    # DUCKDUCKGO SCRAPING
    # ==================
    def search_duckduckgo(self, query: str, num_results: int = 30) -> List[Dict]:
        """
        Durchsucht DuckDuckGo nach dem Suchbegriff
        Verwendet DuckDuckGo HTML-Version (stabiler als JS-Version)
        """
        results = []
        self.search.log_progress(f"DuckDuckGo-Suche: '{query}'")

        try:
            # DuckDuckGo HTML-Suche (Lite-Version, kein JavaScript)
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=de-de"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                self.search.log_progress(f"DuckDuckGo: HTTP {response.status_code}")
                self.source_stats['duckduckgo']['status'] = 'error'
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Mehrere Selektoren versuchen
            selectors = [
                'div.result',  # Standard HTML-Version
                'div.results_links',  # Alternatives Format
                'div.web-result',  # Neueres Format
            ]

            found_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    found_containers = containers
                    self.search.log_progress(f"DuckDuckGo: Verwende Selector '{selector}' ({len(containers)} Container)")
                    break

            for result in found_containers:
                try:
                    # Link finden
                    link_elem = result.select_one('a.result__a') or result.select_one('a[href^="http"]')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')

                    # DuckDuckGo-Weiterleitungs-Links bereinigen
                    if '//duckduckgo.com/l/' in url:
                        # URL aus Parameter extrahieren
                        import urllib.parse as urlparse
                        parsed = urlparse.urlparse(url)
                        params = urlparse.parse_qs(parsed.query)
                        if 'uddg' in params:
                            url = urlparse.unquote(params['uddg'][0])

                    if not self._is_valid_url(url):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    # Beschreibung finden
                    desc_elem = result.select_one('a.result__snippet') or result.select_one('.result__snippet')
                    description = self._clean_text(desc_elem.get_text()) if desc_elem else ''

                    results.append({
                        'url': url,
                        'title': title,
                        'description': description,
                        'source_type': SourceType.DUCKDUCKGO
                    })

                    if len(results) >= num_results:
                        break

                except Exception as e:
                    logger.debug(f"Error parsing DuckDuckGo result: {e}")
                    continue

            self.source_stats['duckduckgo']['found'] = len(results)
            self.source_stats['duckduckgo']['status'] = 'ok' if results else 'warning'
            self.search.log_progress(f"DuckDuckGo: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"DuckDuckGo search error: {e}")
            self.search.log_progress(f"DuckDuckGo-Fehler: {e}")
            self.source_stats['duckduckgo']['status'] = 'error'

        return results

    # ==================
    # ECOSIA SCRAPING
    # ==================
    def search_ecosia(self, query: str, num_results: int = 30) -> List[Dict]:
        """
        Durchsucht Ecosia nach dem Suchbegriff
        """
        results = []
        self.search.log_progress(f"Ecosia-Suche: '{query}'")

        try:
            url = f"https://www.ecosia.org/search?method=index&q={quote_plus(query)}"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                self.search.log_progress(f"Ecosia: HTTP {response.status_code}")
                self.source_stats['ecosia']['status'] = 'error'
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Mehrere Selektoren versuchen (Ecosia ändert HTML manchmal)
            selectors = [
                'article.result',  # Standard
                'div.result',  # Alternatives Format
                'section.mainline__result',  # Neueres Format
                'div[data-test="web-result"]',  # Test-Attribut
            ]

            found_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    found_containers = containers
                    self.search.log_progress(f"Ecosia: Verwende Selector '{selector}' ({len(containers)} Container)")
                    break

            for result in found_containers:
                try:
                    # Link finden
                    link_elem = result.select_one('a.result__link') or result.select_one('a[href^="http"]')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    # Titel finden
                    title_elem = result.select_one('h2.result__title') or result.select_one('h2') or result.select_one('a')
                    title = self._clean_text(title_elem.get_text()) if title_elem else ''

                    # Beschreibung finden
                    desc_elem = result.select_one('p.result__body') or result.select_one('p')
                    description = self._clean_text(desc_elem.get_text()) if desc_elem else ''

                    results.append({
                        'url': url,
                        'title': title,
                        'description': description,
                        'source_type': SourceType.ECOSIA
                    })

                    if len(results) >= num_results:
                        break

                except Exception as e:
                    logger.debug(f"Error parsing Ecosia result: {e}")
                    continue

            self.source_stats['ecosia']['found'] = len(results)
            self.source_stats['ecosia']['status'] = 'ok' if results else 'warning'
            self.search.log_progress(f"Ecosia: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Ecosia search error: {e}")
            self.search.log_progress(f"Ecosia-Fehler: {e}")
            self.source_stats['ecosia']['status'] = 'error'

        return results

    # ==================
    # REDDIT SCRAPING
    # ==================
    def search_reddit(self, query: str, num_results: int = 20) -> List[Dict]:
        """
        Durchsucht Reddit nach relevanten Diskussionen
        Verwendet die alte Reddit-Version für einfacheres Scraping
        """
        results = []
        self.search.log_progress(f"Reddit-Suche: '{query}'")

        try:
            # Reddit-Suche (alte Version - stabiler für Scraping)
            url = f"https://old.reddit.com/search?q={quote_plus(query)}&sort=new&t=year"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                self.search.log_progress(f"Reddit: HTTP {response.status_code}")
                self.source_stats['reddit']['status'] = 'error'
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Mehrere Selektoren versuchen
            selectors = [
                'div.search-result',  # Standard old.reddit Format
                'div.thing',  # Alternatives old.reddit Format
                'div.search-result-link',  # Link-Container
            ]

            found_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    found_containers = containers
                    self.search.log_progress(f"Reddit: Verwende Selector '{selector}' ({len(containers)} Container)")
                    break

            for result in found_containers:
                try:
                    # Link finden
                    link_elem = result.select_one('a.search-title') or result.select_one('a.title') or result.select_one('a[data-click-id="body"]')
                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    if href.startswith('/'):
                        href = f"https://www.reddit.com{href}"
                    elif href.startswith('//'):
                        href = f"https:{href}"

                    if not href.startswith('https://'):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    # Subreddit als Beschreibung
                    subreddit_elem = result.select_one('a.search-subreddit-link') or result.select_one('a.subreddit')
                    subreddit = subreddit_elem.get_text() if subreddit_elem else ''
                    description = f"Subreddit: {subreddit}" if subreddit else ''

                    results.append({
                        'url': href,
                        'title': title,
                        'description': description,
                        'source_type': SourceType.REDDIT
                    })

                    if len(results) >= num_results:
                        break

                except Exception as e:
                    logger.debug(f"Error parsing Reddit result: {e}")
                    continue

            self.source_stats['reddit']['found'] = len(results)
            self.source_stats['reddit']['status'] = 'ok' if results else 'warning'
            self.search.log_progress(f"Reddit: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Reddit search error: {e}")
            self.search.log_progress(f"Reddit-Fehler: {e}")
            self.source_stats['reddit']['status'] = 'error'

        return results

    # ==================
    # YOUTUBE API
    # ==================
    def search_youtube(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Durchsucht YouTube nach relevanten Videos und extrahiert URLs aus Beschreibungen.
        Speichert NICHT das YouTube-Video, sondern die in der Beschreibung verlinkten Seiten.
        """
        results = []
        self.search.log_progress(f"YouTube-Suche: '{query}'")

        # API Key vom User holen
        api_key = None
        if self.search.triggered_by:
            api_key = getattr(self.search.triggered_by, 'youtube_api_key', None)

        if not api_key:
            self.search.log_progress("YouTube: API-Key nicht konfiguriert")
            self.source_stats['youtube']['status'] = 'warning'
            return results

        try:
            # Schritt 1: Videos suchen
            search_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': num_results,
                'order': 'relevance',
                'relevanceLanguage': 'de',
                'regionCode': 'DE',
                'key': api_key
            }

            response = self.session.get(search_url, params=params, timeout=15)

            if response.status_code == 403:
                self.search.log_progress("YouTube: API-Key ungültig oder Quota überschritten")
                self.source_stats['youtube']['status'] = 'error'
                return results
            elif response.status_code != 200:
                self.search.log_progress(f"YouTube: HTTP {response.status_code}")
                self.source_stats['youtube']['status'] = 'error'
                return results

            search_data = response.json()
            video_ids = [item['id']['videoId'] for item in search_data.get('items', [])]

            if not video_ids:
                self.search.log_progress("YouTube: Keine Videos gefunden")
                return results

            # Schritt 2: Volle Video-Details holen (inkl. kompletter Beschreibung)
            videos_url = "https://www.googleapis.com/youtube/v3/videos"
            videos_params = {
                'part': 'snippet',
                'id': ','.join(video_ids),
                'key': api_key
            }

            videos_response = self.session.get(videos_url, params=videos_params, timeout=15)
            if videos_response.status_code != 200:
                self.search.log_progress(f"YouTube Videos API: HTTP {videos_response.status_code}")
                return results

            videos_data = videos_response.json()
            urls_found = 0
            domains_found = 0

            for item in videos_data.get('items', []):
                try:
                    snippet = item['snippet']
                    video_title = sanitize_for_mysql(snippet.get('title', ''))
                    full_description = snippet.get('description', '')
                    channel = sanitize_for_mysql(snippet.get('channelTitle', ''))
                    video_id = item['id']

                    all_urls = set()
                    all_domains = set()

                    # 1. URLs aus Beschreibung extrahieren
                    desc_urls = self._extract_urls_from_text(full_description)
                    all_urls.update(desc_urls)

                    # 2. Untertitel abrufen und Domains extrahieren
                    transcript_text = self._get_youtube_transcript(video_id)
                    if transcript_text:
                        # URLs aus Untertitel
                        transcript_urls = self._extract_urls_from_text(transcript_text)
                        all_urls.update(transcript_urls)

                        # Domain-Erwähnungen aus Untertitel (z.B. "besucht example.de")
                        transcript_domains = self._extract_domains_from_text(transcript_text)
                        all_domains.update(transcript_domains)

                    # Domains auch aus Beschreibung
                    desc_domains = self._extract_domains_from_text(full_description)
                    all_domains.update(desc_domains)

                    # Domains die bereits als URLs gefunden wurden, entfernen
                    for url in all_urls:
                        domain = self._extract_domain(url).lower()
                        all_domains.discard(domain)

                    found_count = len(all_urls) + len(all_domains)
                    if found_count > 0:
                        self.search.log_progress(
                            f"  Video '{video_title[:35]}...' → {len(all_urls)} URLs, {len(all_domains)} Domains"
                        )

                        # Vollständige URLs speichern
                        for url in all_urls:
                            results.append({
                                'url': url,
                                'title': f"Gefunden in: {video_title[:100]}",
                                'description': f"Quelle: YouTube-Video von {channel}\nhttps://youtube.com/watch?v={video_id}",
                                'source_type': SourceType.YOUTUBE
                            })
                            urls_found += 1

                        # Domains als https:// URLs speichern
                        for domain in all_domains:
                            results.append({
                                'url': f"https://{domain}",
                                'title': f"Erwähnt in: {video_title[:100]}",
                                'description': f"Domain im Video erwähnt\nQuelle: YouTube von {channel}\nhttps://youtube.com/watch?v={video_id}",
                                'source_type': SourceType.YOUTUBE
                            })
                            domains_found += 1

                except Exception as e:
                    logger.debug(f"Error parsing YouTube video: {e}")
                    continue

            total_found = urls_found + domains_found
            self.source_stats['youtube']['found'] = total_found
            self.source_stats['youtube']['status'] = 'ok' if total_found > 0 else 'warning'
            self.search.log_progress(
                f"YouTube: {urls_found} URLs + {domains_found} Domains aus {len(video_ids)} Videos"
            )

        except requests.RequestException as e:
            logger.error(f"YouTube API error: {e}")
            self.search.log_progress(f"YouTube-Fehler: {e}")
            self.source_stats['youtube']['status'] = 'error'

        return results

    # ==================
    # TIKTOK SUCHE (via Brave Search + Supadata)
    # ==================
    def search_tiktok(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Durchsucht TikTok-Videos nach relevanten Inhalten.
        1. Findet TikTok-Videos via Brave Search API (site:tiktok.com)
        2. Extrahiert Untertitel via Supadata API
        3. Sucht in Untertiteln nach URLs und Domain-Erwähnungen
        """
        results = []
        self.search.log_progress(f"TikTok-Suche: '{query}'")

        # API Keys prüfen
        supadata_key = None
        brave_key = None
        if self.search.triggered_by:
            supadata_key = getattr(self.search.triggered_by, 'supadata_api_key', None)
            brave_key = getattr(self.search.triggered_by, 'brave_api_key', None)

        if not supadata_key:
            self.search.log_progress("TikTok: Supadata API-Key nicht konfiguriert")
            self.source_stats['tiktok']['status'] = 'warning'
            return results

        if not brave_key:
            self.search.log_progress("TikTok: Brave Search API-Key nicht konfiguriert")
            self.source_stats['tiktok']['status'] = 'warning'
            return results

        try:
            # Schritt 1: TikTok-Videos via Brave Search API finden
            search_query = f"site:tiktok.com {query}"
            brave_url = "https://api.search.brave.com/res/v1/web/search"

            response = self.session.get(
                brave_url,
                params={
                    'q': search_query,
                    'count': 20,
                    'country': 'de',
                    'search_lang': 'de'
                },
                headers={
                    'X-Subscription-Token': brave_key,
                    'Accept': 'application/json'
                },
                timeout=15
            )

            if response.status_code == 401:
                self.search.log_progress("TikTok: Brave API-Key ungültig")
                self.source_stats['tiktok']['status'] = 'error'
                return results

            if response.status_code == 429:
                self.search.log_progress("TikTok: Brave API Rate-Limit erreicht")
                self.source_stats['tiktok']['status'] = 'error'
                return results

            if response.status_code != 200:
                self.search.log_progress(f"TikTok: Brave HTTP {response.status_code}")
                self.source_stats['tiktok']['status'] = 'error'
                return results

            data = response.json()
            web_pages = data.get('web', {}).get('results', [])

            # TikTok-Video-URLs extrahieren
            tiktok_urls = []
            self.search.log_progress(f"TikTok: Brave Search {len(web_pages)} Ergebnisse")
            
            for page in web_pages:
                try:
                    href = page.get('url', '')
                    # Nur TikTok-Video-URLs (/@user/video/ID Format)
                    if 'tiktok.com' in href and '/video/' in href:
                        tiktok_urls.append(href)
                        if len(tiktok_urls) >= num_results:
                            break
                except:
                    continue

            if not tiktok_urls:
                self.search.log_progress(f"TikTok: Keine Videos mit /video/ gefunden")
                self.source_stats['tiktok']['status'] = 'warning'
                return results

            self.search.log_progress(f"TikTok: {len(tiktok_urls)} Videos gefunden, extrahiere Daten...")

            # Schritt 2: Untertitel UND Metadata für jedes Video abrufen
            urls_found = 0
            domains_found = 0

            for video_url in tiktok_urls:
                try:
                    all_urls = set()
                    all_domains = set()
                    video_id = video_url.split('/video/')[-1].split('?')[0][:12] if '/video/' in video_url else video_url[-20:]

                    # Rate-Limit: 1 request/second (Supadata free tier)
                    time.sleep(1.5)

                    # A) Untertitel abrufen (was im Video gesagt wird)
                    transcript_text = self._get_tiktok_transcript(video_url)
                    if transcript_text:
                        transcript_urls = self._extract_urls_from_text(transcript_text)
                        all_urls.update(transcript_urls)
                        transcript_domains = self._extract_domains_from_text(transcript_text)
                        all_domains.update(transcript_domains)

                    # Kurze Pause zwischen API-Aufrufen
                    time.sleep(1.0)

                    # B) Metadata abrufen (Video-Description mit Links)
                    metadata = self._get_tiktok_metadata(video_url)
                    if metadata:
                        description = metadata.get('description', '')
                        if description:
                            # URLs aus Description extrahieren
                            desc_urls = self._extract_urls_from_text(description)
                            all_urls.update(desc_urls)
                            desc_domains = self._extract_domains_from_text(description)
                            all_domains.update(desc_domains)

                    # Domains die bereits als URLs gefunden wurden, entfernen
                    for url_item in all_urls:
                        domain = self._extract_domain(url_item).lower()
                        all_domains.discard(domain)

                    found_count = len(all_urls) + len(all_domains)
                    if found_count > 0:
                        self.search.log_progress(
                            f"  TikTok {video_id}... → {len(all_urls)} URLs, {len(all_domains)} Domains"
                        )

                        # Vollständige URLs speichern
                        for url_item in all_urls:
                            results.append({
                                'url': url_item,
                                'title': f"Gefunden in TikTok-Video",
                                'description': f"Quelle: TikTok-Video\n{video_url}",
                                'source_type': SourceType.TIKTOK
                            })
                            urls_found += 1

                        # Domains als https:// URLs speichern
                        for domain in all_domains:
                            results.append({
                                'url': f"https://{domain}",
                                'title': f"Erwähnt in TikTok-Video",
                                'description': f"Domain im Video erwähnt\nQuelle: TikTok\n{video_url}",
                                'source_type': SourceType.TIKTOK
                            })
                            domains_found += 1

                    # Kurze Pause zwischen Videos
                    self._delay(0.5, 1.0)

                except Exception as e:
                    logger.debug(f"Error processing TikTok video {video_url}: {e}")
                    continue

            total_found = urls_found + domains_found
            self.source_stats['tiktok']['found'] = total_found
            self.source_stats['tiktok']['status'] = 'ok' if total_found > 0 else 'warning'
            self.search.log_progress(
                f"TikTok: {urls_found} URLs + {domains_found} Domains aus {len(tiktok_urls)} Videos"
            )

        except requests.RequestException as e:
            logger.error(f"TikTok search error: {e}")
            self.search.log_progress(f"TikTok-Fehler: {e}")
            self.source_stats['tiktok']['status'] = 'error'

        return results

    # ==================
    # QUALITY SCORE
    # ==================
    def calculate_quality_score(self, result: Dict, category: str) -> int:
        """
        Berechnet einen Qualitätsscore (0-100) basierend auf verschiedenen Faktoren
        """
        score = 50  # Basiswert

        url = result.get('url', '')
        domain = self._extract_domain(url)
        title = result.get('title', '')
        description = result.get('description', '')

        # HTTPS Bonus (+10)
        if url.startswith('https://'):
            score += 10

        # Domain-Länge (kürzere = etablierter) (+5)
        if len(domain) < 15:
            score += 5

        # Bekannte TLDs (+5)
        trusted_tlds = ['.de', '.com', '.org', '.net', '.eu', '.at', '.ch']
        if any(domain.endswith(tld) for tld in trusted_tlds):
            score += 5

        # Titel vorhanden (+5)
        if title and len(title) > 10:
            score += 5

        # Beschreibung vorhanden (+5)
        if description and len(description) > 30:
            score += 5

        # Kategorie-spezifische Boni
        category_bonuses = {
            BacklinkCategory.GUEST_POST: 15,  # Gastbeiträge sind hochwertig
            BacklinkCategory.DIRECTORY: 10,  # Verzeichnisse sind gut
            BacklinkCategory.NEWS: 10,  # Presseportale sind gut
            BacklinkCategory.FORUM: 5,  # Foren sind mittel
            BacklinkCategory.QA: 5,  # Q&A ist mittel
            BacklinkCategory.PROFILE: 0,  # Profile sind Standard
            BacklinkCategory.COMMENT: -5,  # Kommentare sind niedriger
        }
        score += category_bonuses.get(category, 0)

        # Keyword-Indikatoren im Titel/Description
        positive_keywords = ['kostenlos', 'gratis', 'eintragen', 'registrieren', 'gastbeitrag', 'autor']
        negative_keywords = ['spam', 'werbung', 'kostenpflichtig', 'premium', 'abo']

        text = (title + ' ' + description).lower()
        for kw in positive_keywords:
            if kw in text:
                score += 3

        for kw in negative_keywords:
            if kw in text:
                score -= 5

        # Score auf 0-100 begrenzen
        return max(0, min(100, score))

    def is_real_backlink_opportunity(self, result: Dict) -> bool:
        """
        Prüft ob das Ergebnis eine echte Backlink-Möglichkeit ist.
        Filtert Seiten raus, die keine Backlinks anbieten.
        """
        title = result.get('title', '').lower()
        description = result.get('description', '').lower()
        text = title + ' ' + description

        # Muss mindestens eines dieser Wörter enthalten
        backlink_indicators = [
            'backlink', 'dofollow', 'eintragen', 'registrieren',
            'firma hinzufügen', 'unternehmen eintragen', 'kostenlos anmelden',
            'gastbeitrag', 'gastautor', 'artikel einreichen',
            'webkatalog', 'branchenbuch', 'firmenverzeichnis',
            'link eintragen', 'webseite eintragen', 'url eintragen',
            'gratis eintrag', 'kostenloser eintrag', 'free listing'
        ]

        has_indicator = any(indicator in text for indicator in backlink_indicators)

        # Ausschlusskriterien (Agenturen, Tools, Kaufangebote)
        exclude_indicators = [
            # Kaufangebote
            'backlink kaufen', 'links kaufen', 'backlinks kaufen',
            'linkbuilding kaufen', 'seo kaufen', 'backlink bestellen',
            'backlink paket', 'linkpaket', 'ab € ', 'ab eur', 'preis',
            # Agenturen & Dienstleister
            'seo agentur', 'marketing agentur', 'online marketing',
            'linkbuilding agentur', 'linkbuilding service', 'seo service',
            'wir bieten', 'unsere leistung', 'unsere dienstleistung',
            'jetzt anfragen', 'angebot anfordern', 'kostenlose beratung',
            'full service', 'agentur für', 'ihre seo', 'ihr partner',
            # Tools & Analysen
            'backlink checker', 'backlink analyse', 'backlink tool',
            'backlink prüfen', 'backlinks analysieren', 'seo tool',
            # Erklärungen/Definitionen
            'was ist ein backlink', 'backlink definition', 'backlink erklärt',
            'backlink guide', 'backlink tutorial', 'wie funktioniert',
            # Bezahlschranken
            'nur für kunden', 'premium mitglied', 'kostenpflichtig',
            'pro monat', 'pro jahr', 'abo', 'subscription'
        ]

        is_excluded = any(indicator in text for indicator in exclude_indicators)

        return has_indicator and not is_excluded

    def extract_backlink_instructions(self, result: Dict) -> str:
        """
        Extrahiert Anweisungen wie/wo man den Backlink bekommt.
        """
        description = result.get('description', '')
        title = result.get('title', '')
        text = (title + ' ' + description).lower()

        instructions = []

        # Erkenne Verzeichnis-Einträge
        if any(word in text for word in ['firmenverzeichnis', 'branchenbuch', 'webkatalog']):
            instructions.append("Firma/Webseite kostenlos eintragen")
            if 'registrieren' in text or 'anmelden' in text:
                instructions.append("Registrierung erforderlich")

        # Erkenne Gastbeiträge
        if any(word in text for word in ['gastbeitrag', 'gastautor', 'artikel einreichen']):
            instructions.append("Gastbeitrag mit Autorenbox/Bio-Link einreichen")

        # Erkenne Foren/Kommentare
        if 'forum' in text or 'community' in text:
            instructions.append("Profil mit Webseiten-Link erstellen")

        # Erkenne Pressemitteilungen
        if 'presse' in text or 'news' in text:
            instructions.append("Pressemitteilung mit Links veröffentlichen")

        # Fallback
        if not instructions:
            if 'kostenlos' in text:
                instructions.append("Kostenlose Eintragung möglich")
            if 'dofollow' in text:
                instructions.append("DoFollow-Link verfügbar")

        return ' | '.join(instructions) if instructions else ''

    # ==================
    # SPEICHERN
    # ==================
    def save_result(self, result: Dict, search_query: SearchQuery) -> Tuple[bool, bool]:
        """
        Speichert ein Ergebnis in der Datenbank
        Returns: (is_new, is_updated)
        """
        url = result.get('url', '')
        if not url:
            return False, False

        # Qualitätsfilter: Nur echte Backlink-Möglichkeiten speichern
        if not self.is_real_backlink_opportunity(result):
            return False, False

        # Backlink-Anweisungen extrahieren
        instructions = self.extract_backlink_instructions(result)
        if instructions:
            # Füge Anweisungen zur Beschreibung hinzu
            original_desc = result.get('description', '')
            result['description'] = f"[BACKLINK-TIPP] {instructions}\n\n{original_desc}"

        domain = self._extract_domain(url)
        category = search_query.category if search_query else BacklinkCategory.OTHER

        # URL-Hash für Duplikat-Erkennung
        url_hash = BacklinkSource.get_url_hash(url)

        # Prüfen ob bereits vorhanden (über Hash)
        existing = BacklinkSource.objects.filter(url_hash=url_hash).first()

        if existing:
            # Duplikat: last_found aktualisieren
            existing.last_found = timezone.now()
            existing.save(update_fields=['last_found', 'updated_at'])
            return False, True

        # Neuen Eintrag erstellen
        quality_score = self.calculate_quality_score(result, category)

        BacklinkSource.objects.create(
            url=url,
            url_hash=url_hash,
            domain=domain,
            title=sanitize_for_mysql(result.get('title', ''))[:500],
            description=sanitize_for_mysql(result.get('description', ''))[:1000],
            category=category,
            source_type=result.get('source_type', SourceType.MANUAL),
            search_query=search_query,
            quality_score=quality_score,
            first_found=timezone.now(),
            last_found=timezone.now()
        )

        return True, False

    # ==================
    # HAUPTMETHODE
    # ==================
    def run(self, sources: List[str] = None) -> Dict:
        """
        Führt die komplette Backlink-Suche durch

        Args:
            sources: Liste der zu verwendenden Quellen (duckduckgo, reddit, youtube, tiktok)
                     Wenn None, werden alle aktiven Quellen verwendet
        """
        # Standard-Quellen wenn nicht angegeben (nur funktionierende)
        if sources is None:
            sources = ['duckduckgo', 'youtube']

        self.search.start()
        self.search.log_progress("Starte Backlink-Suche...")

        # Quellen-Namen für Anzeige
        source_names = []
        if 'duckduckgo' in sources:
            source_names.append('DuckDuckGo')
        if 'reddit' in sources:
            source_names.append('Reddit')
        if 'youtube' in sources:
            source_names.append('YouTube')
        if 'tiktok' in sources:
            source_names.append('TikTok')

        self.search.log_progress(f"Ausgewählte Quellen: {', '.join(source_names)}")

        try:
            # Alle aktiven Suchbegriffe laden
            queries = SearchQuery.objects.filter(is_active=True).order_by('-priority')

            if not queries.exists():
                self.search.log_progress("Keine aktiven Suchbegriffe gefunden!")
                self.search.complete(0, 0, 0)
                return self.stats

            total_queries = queries.count()
            self.search.log_progress(f"{total_queries} Suchbegriffe werden verarbeitet...")

            for i, query in enumerate(queries):
                self.search.log_progress(f"\n--- Suchbegriff {i+1}/{total_queries}: '{query.query}' ---")

                all_results = []

                # DuckDuckGo (nur wenn ausgewählt)
                if 'duckduckgo' in sources:
                    self._delay(2, 4)
                    all_results.extend(self.search_duckduckgo(query.query))

                # Reddit (nur wenn ausgewählt)
                if 'reddit' in sources:
                    self._delay(2, 4)
                    all_results.extend(self.search_reddit(query.query))

                # YouTube (nur wenn ausgewählt)
                if 'youtube' in sources:
                    self._delay(1, 2)
                    all_results.extend(self.search_youtube(query.query))

                # TikTok (nur wenn ausgewählt)
                if 'tiktok' in sources:
                    self._delay(1, 2)
                    all_results.extend(self.search_tiktok(query.query))

                # Ergebnisse speichern
                for result in all_results:
                    try:
                        is_new, is_updated = self.save_result(result, query)
                        self.stats['found'] += 1
                        if is_new:
                            self.stats['new'] += 1
                        elif is_updated:
                            self.stats['updated'] += 1
                    except Exception as e:
                        logger.error(f"Error saving result: {e}")
                        self.stats['errors'] += 1

                self.search.log_progress(
                    f"Zwischenstand: {self.stats['new']} neue, "
                    f"{self.stats['updated']} aktualisiert"
                )

                # MySQL-Verbindung alle 3 Keywords erneuern (verhindert Timeout)
                if (i + 1) % 3 == 0:
                    connection.close()

                # Kürzere Pause zwischen Suchbegriffen (weniger Quellen)
                self._delay(3, 5)

            # Suche abschließen
            self.search.complete(
                sources_found=self.stats['found'],
                new_sources=self.stats['new'],
                updated_sources=self.stats['updated']
            )

            self.search.log_progress(
                f"\n=== ABGESCHLOSSEN ===\n"
                f"Gefunden: {self.stats['found']}\n"
                f"Neu: {self.stats['new']}\n"
                f"Aktualisiert: {self.stats['updated']}\n"
                f"Fehler: {self.stats['errors']}"
            )

        except Exception as e:
            logger.exception("Backlink search failed")
            self.search.fail(str(e))
            raise

        return self.stats


def run_backlink_search(user, sources: List[str] = None) -> BacklinkSearch:
    """
    Startet eine neue Backlink-Suche (asynchron in einem Thread)

    Args:
        user: Der User der die Suche startet
        sources: Liste der zu verwendenden Quellen (duckduckgo, reddit, youtube)
                 Wenn None, werden alle aktiven Quellen verwendet
    """
    import threading

    # Neue Suche erstellen
    search = BacklinkSearch.objects.create(triggered_by=user)

    def run_search_async():
        """Führt die Suche in einem separaten Thread aus"""
        try:
            from django.db import connection
            # Neue DB-Verbindung für den Thread
            connection.close()

            # Search-Objekt im neuen Thread frisch laden
            fresh_search = BacklinkSearch.objects.get(pk=search.pk)
            scraper = BacklinkScraper(fresh_search)
            scraper.run(sources=sources)
        except Exception as e:
            logger.exception(f"Error in async backlink search: {e}")
            # Search-Objekt neu laden und Fehler speichern
            try:
                from django.db import connection
                connection.close()
                search_obj = BacklinkSearch.objects.get(pk=search.pk)
                search_obj.status = BacklinkSearchStatus.FAILED
                search_obj.error_log = str(e)
                search_obj.save()
            except:
                pass

    # Suche in separatem Thread starten
    thread = threading.Thread(target=run_search_async, daemon=True)
    thread.start()

    return search


def cleanup_old_sources(months: int = 12) -> int:
    """
    Löscht Backlink-Quellen die älter als X Monate sind
    """
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=months * 30)
    deleted_count, _ = BacklinkSource.objects.filter(
        last_found__lt=cutoff_date
    ).delete()

    logger.info(f"Deleted {deleted_count} backlink sources older than {months} months")
    return deleted_count


def initialize_default_queries() -> int:
    """
    Initialisiert die vordefinierten Suchbegriffe
    """
    from .default_queries import DEFAULT_SEARCH_QUERIES

    created_count = 0

    for query_data in DEFAULT_SEARCH_QUERIES:
        _, created = SearchQuery.objects.get_or_create(
            query=query_data['query'],
            defaults={
                'category': query_data['category'],
                'description': query_data.get('description', ''),
                'priority': query_data.get('priority', 5),
                'is_active': True
            }
        )
        if created:
            created_count += 1

    logger.info(f"Initialized {created_count} default search queries")
    return created_count

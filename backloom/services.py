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
from django.utils import timezone

from .models import (
    BacklinkCategory,
    BacklinkSearch,
    BacklinkSource,
    SearchQuery,
    SourceType,
)

logger = logging.getLogger(__name__)

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
                logger.warning(f"Google returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Suchergebnisse parsen
            for result in soup.select('div.g'):
                try:
                    link_elem = result.select_one('a[href]')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    title_elem = result.select_one('h3')
                    title = self._clean_text(title_elem.get_text()) if title_elem else ''

                    desc_elem = result.select_one('div[data-sncf], div.VwiC3b')
                    description = self._clean_text(desc_elem.get_text()) if desc_elem else ''

                    results.append({
                        'url': url,
                        'title': title,
                        'description': description,
                        'source_type': SourceType.GOOGLE
                    })

                except Exception as e:
                    logger.debug(f"Error parsing Google result: {e}")
                    continue

            self.search.log_progress(f"Google: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Google search error: {e}")
            self.search.log_progress(f"Google-Fehler: {e}")

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
                logger.warning(f"Bing returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Suchergebnisse parsen
            for result in soup.select('li.b_algo'):
                try:
                    link_elem = result.select_one('h2 a')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    desc_elem = result.select_one('div.b_caption p')
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

            self.search.log_progress(f"Bing: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Bing search error: {e}")
            self.search.log_progress(f"Bing-Fehler: {e}")

        return results

    # ==================
    # DUCKDUCKGO SCRAPING
    # ==================
    def search_duckduckgo(self, query: str, num_results: int = 30) -> List[Dict]:
        """
        Durchsucht DuckDuckGo nach dem Suchbegriff
        Verwendet DuckDuckGo HTML-Version
        """
        results = []
        self.search.log_progress(f"DuckDuckGo-Suche: '{query}'")

        try:
            # DuckDuckGo HTML-Suche
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=de-de"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"DuckDuckGo returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Suchergebnisse parsen
            for result in soup.select('div.result'):
                try:
                    link_elem = result.select_one('a.result__a')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    desc_elem = result.select_one('a.result__snippet')
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

            self.search.log_progress(f"DuckDuckGo: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"DuckDuckGo search error: {e}")
            self.search.log_progress(f"DuckDuckGo-Fehler: {e}")

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
                logger.warning(f"Ecosia returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Suchergebnisse parsen
            for result in soup.select('article.result'):
                try:
                    link_elem = result.select_one('a.result__link')
                    if not link_elem:
                        continue

                    url = link_elem.get('href', '')
                    if not self._is_valid_url(url):
                        continue

                    title_elem = result.select_one('h2.result__title')
                    title = self._clean_text(title_elem.get_text()) if title_elem else ''

                    desc_elem = result.select_one('p.result__body')
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

            self.search.log_progress(f"Ecosia: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Ecosia search error: {e}")
            self.search.log_progress(f"Ecosia-Fehler: {e}")

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
            # Reddit-Suche (alte Version)
            url = f"https://old.reddit.com/search?q={quote_plus(query)}&sort=new&t=year"

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"Reddit returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Suchergebnisse parsen
            for result in soup.select('div.search-result'):
                try:
                    link_elem = result.select_one('a.search-title')
                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    if href.startswith('/'):
                        href = f"https://www.reddit.com{href}"

                    if not href.startswith('https://'):
                        continue

                    title = self._clean_text(link_elem.get_text())

                    # Subreddit als Beschreibung
                    subreddit_elem = result.select_one('a.search-subreddit-link')
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

            self.search.log_progress(f"Reddit: {len(results)} Ergebnisse gefunden")

        except requests.RequestException as e:
            logger.error(f"Reddit search error: {e}")
            self.search.log_progress(f"Reddit-Fehler: {e}")

        return results

    # ==================
    # YOUTUBE API
    # ==================
    def search_youtube(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Durchsucht YouTube nach relevanten Videos
        Verwendet YouTube Data API v3
        """
        results = []
        self.search.log_progress(f"YouTube-Suche: '{query}'")

        # API Key vom User holen (aus Profil-Einstellungen)
        api_key = None
        if self.search.triggered_by:
            api_key = getattr(self.search.triggered_by, 'youtube_api_key', None)

        if not api_key:
            self.search.log_progress("YouTube-API-Key nicht konfiguriert (in Profil-Einstellungen hinterlegen)")
            return results

        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': num_results,
                'order': 'date',
                'relevanceLanguage': 'de',
                'regionCode': 'DE',
                'key': api_key
            }

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"YouTube API returned status {response.status_code}")
                return results

            data = response.json()

            for item in data.get('items', []):
                try:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']

                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    title = snippet.get('title', '')
                    description = snippet.get('description', '')[:300]
                    channel = snippet.get('channelTitle', '')

                    results.append({
                        'url': video_url,
                        'title': title,
                        'description': f"Kanal: {channel}\n{description}",
                        'source_type': SourceType.YOUTUBE
                    })

                except Exception as e:
                    logger.debug(f"Error parsing YouTube result: {e}")
                    continue

            self.search.log_progress(f"YouTube: {len(results)} Videos gefunden")

        except requests.RequestException as e:
            logger.error(f"YouTube API error: {e}")
            self.search.log_progress(f"YouTube-Fehler: {e}")

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
            title=result.get('title', '')[:500],
            description=result.get('description', '')[:1000],
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
    def run(self) -> Dict:
        """
        Führt die komplette Backlink-Suche durch
        """
        self.search.start()
        self.search.log_progress("Starte Backlink-Suche...")

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

                # Suchmaschinen durchsuchen
                # Google
                self._delay(1, 3)
                all_results.extend(self.search_google(query.query))

                # Bing
                self._delay(2, 4)
                all_results.extend(self.search_bing(query.query))

                # DuckDuckGo
                self._delay(2, 4)
                all_results.extend(self.search_duckduckgo(query.query))

                # Ecosia
                self._delay(2, 4)
                all_results.extend(self.search_ecosia(query.query))

                # Reddit (für alle Kategorien relevant)
                self._delay(2, 4)
                all_results.extend(self.search_reddit(query.query))

                # YouTube (nur für Video-Kategorie)
                if query.category == BacklinkCategory.VIDEO:
                    self._delay(1, 2)
                    all_results.extend(self.search_youtube(query.query))

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

                # Längere Pause zwischen Suchbegriffen
                self._delay(5, 10)

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


def run_backlink_search(user) -> BacklinkSearch:
    """
    Startet eine neue Backlink-Suche
    """
    # Neue Suche erstellen
    search = BacklinkSearch.objects.create(triggered_by=user)

    # Scraper starten
    scraper = BacklinkScraper(search)
    scraper.run()

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

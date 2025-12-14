"""
Web Research Service für BlogPrep

Verantwortlich für:
- Echte Web-Suche via DuckDuckGo (kostenlos, keine API nötig)
- Extraktion von Inhalten aus Top-Suchergebnissen
- Strukturierte Aufbereitung für KI-Analyse
"""

import logging
import requests
import re
import time
import random
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebResearchService:
    """Service für echte Web-Recherche"""

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.timeout = 15

    def search_and_analyze(self, keyword: str, num_results: int = 5) -> Dict:
        """
        Führt eine echte Web-Suche durch und extrahiert Inhalte.

        Args:
            keyword: Das zu suchende Keyword
            num_results: Anzahl der zu analysierenden Ergebnisse (Standard: 5)

        Returns:
            Dict mit success, search_results (Liste von Ergebnissen mit Inhalt)
        """
        try:
            # Schritt 1: Suchergebnisse von DuckDuckGo holen
            search_results = self._search_duckduckgo(keyword, num_results)

            if not search_results:
                logger.warning(f"Keine Suchergebnisse für '{keyword}'")
                return {
                    'success': False,
                    'error': 'Keine Suchergebnisse gefunden',
                    'search_results': []
                }

            logger.info(f"Gefunden: {len(search_results)} Suchergebnisse für '{keyword}'")

            # Schritt 2: Inhalte der gefundenen Seiten extrahieren
            enriched_results = []
            for i, result in enumerate(search_results[:num_results]):
                try:
                    # Kleine Pause zwischen Requests
                    if i > 0:
                        time.sleep(random.uniform(0.5, 1.5))

                    # Seiteninhalt extrahieren
                    content = self._extract_page_content(result['url'])
                    result['content'] = content
                    result['content_preview'] = content[:500] + '...' if len(content) > 500 else content
                    enriched_results.append(result)

                    logger.info(f"Inhalt extrahiert: {result['url'][:50]}... ({len(content)} Zeichen)")

                except Exception as e:
                    logger.warning(f"Fehler beim Extrahieren von {result.get('url', 'unbekannt')}: {e}")
                    # Trotzdem hinzufügen, auch ohne Content
                    result['content'] = ''
                    result['content_preview'] = ''
                    enriched_results.append(result)

            return {
                'success': True,
                'keyword': keyword,
                'search_results': enriched_results,
                'total_results': len(enriched_results)
            }

        except Exception as e:
            logger.error(f"Web-Recherche-Fehler: {e}")
            return {
                'success': False,
                'error': str(e),
                'search_results': []
            }

    def _search_duckduckgo(self, keyword: str, num_results: int = 5) -> List[Dict]:
        """
        Sucht via DuckDuckGo HTML-Suche (keine API nötig).

        Returns:
            Liste von {title, url, snippet}
        """
        results = []

        try:
            # DuckDuckGo HTML-Suche (lite Version für bessere Kompatibilität)
            search_url = "https://lite.duckduckgo.com/lite/"
            params = {
                'q': keyword,
                'kl': 'de-de',  # Deutsche Ergebnisse
            }

            response = self.session.post(
                search_url,
                data=params,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            if response.status_code != 200:
                logger.warning(f"DuckDuckGo Lite Statuscode: {response.status_code}")
                # Fallback zu normaler DuckDuckGo-Suche
                return self._search_duckduckgo_html(keyword, num_results)

            soup = BeautifulSoup(response.text, 'html.parser')

            # Links aus der Lite-Version extrahieren
            for link in soup.find_all('a', class_='result-link'):
                if len(results) >= num_results:
                    break

                href = link.get('href', '')
                title = link.get_text(strip=True)

                if href and title and not self._is_ad_or_blocked(href):
                    # Snippet finden (nächstes Text-Element)
                    snippet = ''
                    snippet_elem = link.find_next('td', class_='result-snippet')
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)

                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': snippet,
                        'position': len(results) + 1
                    })

            # Wenn Lite nicht funktioniert, HTML-Version versuchen
            if not results:
                return self._search_duckduckgo_html(keyword, num_results)

        except Exception as e:
            logger.error(f"DuckDuckGo Lite Suche fehlgeschlagen: {e}")
            # Fallback
            return self._search_duckduckgo_html(keyword, num_results)

        return results

    def _search_duckduckgo_html(self, keyword: str, num_results: int = 5) -> List[Dict]:
        """
        Fallback: DuckDuckGo HTML-Suche
        """
        results = []

        try:
            search_url = f"https://html.duckduckgo.com/html/"
            params = {
                'q': keyword,
                'kl': 'de-de',
            }

            response = self.session.post(
                search_url,
                data=params,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"DuckDuckGo HTML Status: {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ergebnisse parsen
            for result_div in soup.find_all('div', class_='result'):
                if len(results) >= num_results:
                    break

                # Titel und URL
                title_link = result_div.find('a', class_='result__a')
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                url = title_link.get('href', '')

                # URL dekodieren (DuckDuckGo enkodiert URLs)
                if url.startswith('/'):
                    # Relative URL - extrahiere echte URL aus uddg Parameter
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                    if 'uddg' in parsed:
                        url = parsed['uddg'][0]

                if not url or self._is_ad_or_blocked(url):
                    continue

                # Snippet
                snippet_div = result_div.find('a', class_='result__snippet')
                snippet = snippet_div.get_text(strip=True) if snippet_div else ''

                results.append({
                    'title': title,
                    'url': url,
                    'snippet': snippet,
                    'position': len(results) + 1
                })

        except Exception as e:
            logger.error(f"DuckDuckGo HTML Fehler: {e}")

        return results

    def _is_ad_or_blocked(self, url: str) -> bool:
        """Prüft ob URL eine Werbung oder blockierte Domain ist"""
        blocked_domains = [
            'ad.', 'ads.', 'advertising.',
            'doubleclick', 'googlesyndication',
            'facebook.com', 'twitter.com', 'instagram.com',
            'youtube.com', 'tiktok.com',
            'wikipedia.org',  # Wikipedia oft zu generisch
            'amazon.', 'ebay.',  # Shopping-Seiten
        ]

        url_lower = url.lower()
        for blocked in blocked_domains:
            if blocked in url_lower:
                return True

        return False

    def _extract_page_content(self, url: str, max_length: int = 3000) -> str:
        """
        Extrahiert den Hauptinhalt einer Webseite.

        Args:
            url: Die URL der Seite
            max_length: Maximale Länge des extrahierten Textes

        Returns:
            Bereinigter Text-Inhalt der Seite
        """
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            if response.status_code != 200:
                return ''

            # Encoding erkennen
            response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # Entferne unwichtige Elemente
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer',
                                       'aside', 'form', 'iframe', 'noscript']):
                tag.decompose()

            # Versuche den Hauptinhalt zu finden
            content = ''

            # Verschiedene Content-Container probieren
            main_selectors = [
                'article',
                'main',
                '[role="main"]',
                '.post-content',
                '.entry-content',
                '.article-content',
                '.content',
                '#content',
                '.blog-post',
                '.post-body',
            ]

            for selector in main_selectors:
                main_elem = soup.select_one(selector)
                if main_elem:
                    content = self._clean_text(main_elem.get_text())
                    if len(content) > 200:  # Mindestens etwas Inhalt
                        break

            # Fallback: Body-Text
            if not content or len(content) < 200:
                body = soup.find('body')
                if body:
                    content = self._clean_text(body.get_text())

            # Auf maximale Länge beschränken
            if len(content) > max_length:
                # An Satzende abschneiden
                content = content[:max_length]
                last_period = content.rfind('.')
                if last_period > max_length * 0.7:
                    content = content[:last_period + 1]

            return content

        except Exception as e:
            logger.warning(f"Content-Extraktion fehlgeschlagen für {url}: {e}")
            return ''

    def _clean_text(self, text: str) -> str:
        """Bereinigt extrahierten Text"""
        if not text:
            return ''

        # Mehrfache Whitespaces reduzieren
        text = re.sub(r'\s+', ' ', text)

        # Mehrfache Newlines reduzieren
        text = re.sub(r'\n\s*\n', '\n\n', text)

        # Führende/trailing Whitespace entfernen
        text = text.strip()

        return text

    def format_for_llm(self, search_results: List[Dict]) -> str:
        """
        Formatiert Suchergebnisse für die LLM-Analyse.

        Args:
            search_results: Liste von Suchergebnissen mit Inhalt

        Returns:
            Formatierter String für LLM-Prompt
        """
        formatted = []

        for i, result in enumerate(search_results, 1):
            formatted.append(f"""
=== SUCHERGEBNIS {i} ===
Titel: {result.get('title', 'Kein Titel')}
URL: {result.get('url', '')}
Snippet: {result.get('snippet', '')}

SEITENINHALT:
{result.get('content', result.get('content_preview', 'Kein Inhalt verfügbar'))}
""")

        return '\n'.join(formatted)

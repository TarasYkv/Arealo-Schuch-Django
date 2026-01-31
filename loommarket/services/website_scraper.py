"""
Website Scraper für LoomMarket.
Extrahiert Impressum/Imprint von Webseiten.
"""
import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class WebsiteScraper:
    """
    Scraper für Impressum-Daten von Webseiten.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    TIMEOUT = 15

    # Typische Impressum-URL-Patterns
    IMPRESSUM_PATTERNS = [
        '/impressum',
        '/imprint',
        '/legal',
        '/rechtliches',
        '/kontakt',
        '/contact',
        '/about',
        '/ueber-uns',
        '/about-us',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def find_impressum(self, website_url: str) -> Dict[str, Any]:
        """
        Sucht und extrahiert das Impressum einer Website.

        Args:
            website_url: URL der Website

        Returns:
            Dict mit impressum_text, impressum_url, success, error
        """
        result = {
            'success': False,
            'impressum_text': None,
            'impressum_url': None,
            'error': None,
        }

        if not website_url:
            result['error'] = 'Keine Website-URL angegeben'
            return result

        try:
            # URL normalisieren
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url

            logger.info(f"Searching impressum on: {website_url}")

            # Hauptseite laden
            response = self.session.get(website_url, timeout=self.TIMEOUT)
            if response.status_code != 200:
                result['error'] = f'Website nicht erreichbar (Status {response.status_code})'
                return result

            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = f"{urlparse(website_url).scheme}://{urlparse(website_url).netloc}"

            # 1. Impressum-Link auf der Seite suchen
            impressum_url = self._find_impressum_link(soup, base_url)

            if impressum_url:
                result['impressum_url'] = impressum_url
                # Impressum-Seite laden
                impressum_response = self.session.get(impressum_url, timeout=self.TIMEOUT)
                if impressum_response.status_code == 200:
                    impressum_soup = BeautifulSoup(impressum_response.text, 'html.parser')
                    result['impressum_text'] = self._extract_impressum_content(impressum_soup)
                    result['success'] = True
                    return result

            # 2. Typische URLs durchprobieren
            for pattern in self.IMPRESSUM_PATTERNS:
                test_url = urljoin(base_url, pattern)
                try:
                    test_response = self.session.get(test_url, timeout=self.TIMEOUT)
                    if test_response.status_code == 200:
                        test_soup = BeautifulSoup(test_response.text, 'html.parser')
                        impressum_text = self._extract_impressum_content(test_soup)
                        if impressum_text and len(impressum_text) > 50:
                            result['impressum_url'] = test_url
                            result['impressum_text'] = impressum_text
                            result['success'] = True
                            return result
                except:
                    continue

            # 3. Impressum im Footer der Hauptseite suchen
            footer_impressum = self._extract_footer_impressum(soup)
            if footer_impressum:
                result['impressum_text'] = footer_impressum
                result['impressum_url'] = website_url
                result['success'] = True
                return result

            result['error'] = 'Kein Impressum gefunden'

        except requests.Timeout:
            result['error'] = 'Timeout beim Abrufen der Website'
        except requests.RequestException as e:
            result['error'] = f'Netzwerkfehler: {str(e)}'
        except Exception as e:
            result['error'] = f'Fehler: {str(e)}'
            logger.exception(f"Error scraping website: {e}")

        return result

    def _find_impressum_link(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Sucht nach Impressum-Links auf der Seite."""
        keywords = ['impressum', 'imprint', 'legal', 'rechtlich', 'kontakt', 'contact']

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()

            # Prüfe href und Link-Text
            if any(kw in href or kw in text for kw in keywords):
                full_url = urljoin(base_url, link['href'])
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    return full_url

        return None

    def _extract_impressum_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert den Impressum-Inhalt."""
        # Script und Style entfernen
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()

        # Suche nach main content
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=re.compile(r'content|main|impressum|legal', re.I)) or
            soup.find('body')
        )

        if not main_content:
            return None

        # Text extrahieren und bereinigen
        text = main_content.get_text(separator='\n', strip=True)

        # Zeilen bereinigen
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        # Auf vernünftige Länge kürzen
        if len(text) > 3000:
            text = text[:3000] + '...'

        return text if len(text) > 30 else None

    def _extract_footer_impressum(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Impressum-Daten aus dem Footer."""
        footer = soup.find('footer')
        if not footer:
            return None

        # Suche nach Adresse/Kontakt im Footer
        text = footer.get_text(separator='\n', strip=True)

        # Prüfe ob typische Impressum-Inhalte vorhanden
        if any(kw in text.lower() for kw in ['gmbh', 'gbr', 'ug', 'e.k.', 'geschäftsführer', 'handelsregister', 'ust-id']):
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines[:20])  # Erste 20 Zeilen

        return None

    def extract_instagram_impressum(self, bio: str) -> Optional[str]:
        """
        Extrahiert Impressum-relevante Daten aus Instagram Bio.
        """
        if not bio:
            return None

        # Instagram Bio ist das "Impressum" auf Instagram
        return bio

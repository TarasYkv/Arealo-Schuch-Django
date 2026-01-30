"""
Instagram Profile Scraper für LoomMarket.
Extrahiert Profil-Daten (Name, Bio, Website) ohne API.
"""
import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class InstagramScraper:
    """
    Scraper für öffentliche Instagram-Profile.
    Extrahiert nur Meta-Daten, keine Bilder.
    """

    # User-Agent für Requests
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Instagram Profile URL Pattern
    PROFILE_URL_TEMPLATE = "https://www.instagram.com/{username}/"

    # Timeout für Requests
    TIMEOUT = 15

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def normalize_username(self, username: str) -> str:
        """
        Normalisiert Instagram-Username.
        Entfernt @ und URL-Teile.
        """
        username = username.strip()

        # URL extrahieren
        if 'instagram.com' in username:
            parsed = urlparse(username)
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts:
                username = path_parts[0]

        # @ entfernen
        if username.startswith('@'):
            username = username[1:]

        return username.lower()

    def scrape_profile(self, username: str) -> Dict[str, Any]:
        """
        Scrapt ein öffentliches Instagram-Profil.

        Args:
            username: Instagram Username (mit oder ohne @)

        Returns:
            Dict mit Profildaten oder Fehlermeldung
        """
        username = self.normalize_username(username)
        url = self.PROFILE_URL_TEMPLATE.format(username=username)

        result = {
            'success': False,
            'username': username,
            'name': None,
            'bio': None,
            'website': None,
            'follower_count': 0,
            'profile_picture_url': None,
            'error': None,
        }

        try:
            logger.info(f"Scraping Instagram profile: @{username}")

            response = self.session.get(url, timeout=self.TIMEOUT)

            if response.status_code == 404:
                result['error'] = f"Profil @{username} nicht gefunden"
                return result

            if response.status_code != 200:
                result['error'] = f"Fehler beim Abrufen (Status {response.status_code})"
                return result

            # HTML parsen
            soup = BeautifulSoup(response.text, 'html.parser')

            # Meta-Tags extrahieren
            result = self._extract_from_meta_tags(soup, result)

            # JSON-LD Daten extrahieren (falls vorhanden)
            result = self._extract_from_json_ld(soup, result)

            # Fallback: OG-Tags
            result = self._extract_from_og_tags(soup, result)

            # Website aus Bio extrahieren (falls nicht im Profil)
            if not result['website'] and result['bio']:
                result['website'] = self._extract_website_from_text(result['bio'])

            result['success'] = True
            logger.info(f"Successfully scraped @{username}: {result['name']}")

        except requests.Timeout:
            result['error'] = "Timeout beim Abrufen des Profils"
            logger.warning(f"Timeout scraping @{username}")
        except requests.RequestException as e:
            result['error'] = f"Netzwerkfehler: {str(e)}"
            logger.error(f"Request error scraping @{username}: {e}")
        except Exception as e:
            result['error'] = f"Unerwarteter Fehler: {str(e)}"
            logger.exception(f"Error scraping @{username}")

        return result

    def _extract_from_meta_tags(self, soup: BeautifulSoup, result: Dict) -> Dict:
        """Extrahiert Daten aus Standard Meta-Tags."""

        # Title Tag (enthält oft den Namen)
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            # Format: "Name (@username) • Instagram photos and videos"
            name_match = re.match(r'^(.+?)\s*\(@', title_text)
            if name_match:
                result['name'] = name_match.group(1).strip()

        # Description Tag (enthält oft Bio und Follower)
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            desc = desc_tag['content']

            # Follower extrahieren
            follower_match = re.search(r'([\d,\.]+)\s*Follower', desc, re.IGNORECASE)
            if follower_match:
                follower_str = follower_match.group(1).replace(',', '').replace('.', '')
                try:
                    result['follower_count'] = int(follower_str)
                except ValueError:
                    pass

            # Bio ist oft nach "-" oder ":"
            bio_match = re.search(r'[-–]\s*(.+?)(?:\s*$|\s*„)', desc)
            if bio_match:
                result['bio'] = bio_match.group(1).strip()

        return result

    def _extract_from_og_tags(self, soup: BeautifulSoup, result: Dict) -> Dict:
        """Extrahiert Daten aus Open Graph Tags."""

        # OG Image (Profilbild)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            result['profile_picture_url'] = og_image['content']

        # OG Title (Name)
        if not result['name']:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content']
                name_match = re.match(r'^(.+?)\s*\(@', title)
                if name_match:
                    result['name'] = name_match.group(1).strip()
                elif '(' not in title:
                    result['name'] = title.strip()

        # OG Description (Bio)
        if not result['bio']:
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                desc = og_desc['content']
                # Typisches Format: "X Followers, Y Following, Z Posts - See..."
                parts = desc.split(' - ')
                if len(parts) > 1:
                    result['bio'] = ' - '.join(parts[1:]).strip()

        return result

    def _extract_from_json_ld(self, soup: BeautifulSoup, result: Dict) -> Dict:
        """Extrahiert Daten aus JSON-LD strukturierten Daten."""
        import json

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)

                if isinstance(data, dict):
                    # Person/Organization Schema
                    if data.get('@type') in ['Person', 'Organization', 'ProfilePage']:
                        if 'name' in data and not result['name']:
                            result['name'] = data['name']
                        if 'description' in data and not result['bio']:
                            result['bio'] = data['description']
                        if 'url' in data and 'instagram.com' not in data['url']:
                            result['website'] = data['url']
                        if 'image' in data and not result['profile_picture_url']:
                            if isinstance(data['image'], str):
                                result['profile_picture_url'] = data['image']
                            elif isinstance(data['image'], dict):
                                result['profile_picture_url'] = data['image'].get('url')

            except (json.JSONDecodeError, TypeError):
                continue

        return result

    def _extract_website_from_text(self, text: str) -> Optional[str]:
        """
        Extrahiert Website-URL aus Text (Bio).
        """
        if not text:
            return None

        # URL Pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)

        # Erste URL, die nicht Instagram/Facebook ist
        for url in urls:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not any(social in domain for social in ['instagram.com', 'facebook.com', 'fb.com', 'linktr.ee']):
                return url

        # Linktree als Fallback
        for url in urls:
            if 'linktr.ee' in url:
                return url

        return None

    def get_profile_data_for_business(self, username: str) -> Dict[str, Any]:
        """
        Convenience-Methode für Business-Model.
        Gibt aufbereitete Daten zurück.
        """
        profile_data = self.scrape_profile(username)

        return {
            'instagram_username': profile_data['username'],
            'name': profile_data['name'],
            'bio': profile_data['bio'],
            'website': profile_data['website'],
            'follower_count': profile_data['follower_count'],
            'profile_picture_url': profile_data['profile_picture_url'],
            'success': profile_data['success'],
            'error': profile_data['error'],
        }

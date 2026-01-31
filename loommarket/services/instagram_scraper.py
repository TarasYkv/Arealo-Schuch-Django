"""
Instagram Profile Scraper für LoomMarket.
Extrahiert Profil-Daten (Name, Bio, Website) ohne API.

Verwendet mehrere Methoden:
1. Instagram Web API (GraphQL)
2. Mobile Web Version
3. HTML Meta-Tags als Fallback
"""
import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote
from typing import Optional, Dict, Any
import time
import random

logger = logging.getLogger(__name__)


class InstagramScraper:
    """
    Scraper für öffentliche Instagram-Profile.
    Extrahiert nur Meta-Daten, keine Bilder.
    """

    # User-Agents für verschiedene Methoden
    USER_AGENTS = {
        'desktop': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        'mobile': (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        'instagram_app': (
            "Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; "
            "samsung; SM-G991B; o1s; exynos2100; de_DE; 458229237)"
        ),
    }

    # Instagram URLs
    PROFILE_URL_TEMPLATE = "https://www.instagram.com/{username}/"
    MOBILE_URL_TEMPLATE = "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    GRAPHQL_URL = "https://www.instagram.com/graphql/query/"

    # Timeout für Requests
    TIMEOUT = 20

    def __init__(self):
        self.session = requests.Session()

    def _get_desktop_headers(self) -> Dict[str, str]:
        """Headers für Desktop-Anfragen."""
        return {
            'User-Agent': self.USER_AGENTS['desktop'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

    def _get_api_headers(self) -> Dict[str, str]:
        """Headers für Instagram API-Anfragen."""
        return {
            'User-Agent': self.USER_AGENTS['instagram_app'],
            'Accept': '*/*',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-IG-App-ID': '936619743392459',  # Instagram Web App ID
            'X-ASBD-ID': '129477',
            'X-IG-WWW-Claim': '0',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }

    def _get_graphql_headers(self) -> Dict[str, str]:
        """Headers für GraphQL-Anfragen."""
        return {
            'User-Agent': self.USER_AGENTS['desktop'],
            'Accept': '*/*',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-IG-App-ID': '936619743392459',
            'X-ASBD-ID': '129477',
            'X-CSRFToken': 'missing',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

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
        Versucht mehrere Methoden.

        Args:
            username: Instagram Username (mit oder ohne @)

        Returns:
            Dict mit Profildaten oder Fehlermeldung
        """
        username = self.normalize_username(username)

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

        logger.info(f"Scraping Instagram profile: @{username}")

        # Methode 1: Instagram Web Profile Info API
        api_result = self._try_web_profile_api(username)
        if api_result.get('success'):
            logger.info(f"Method 1 (Web API) successful for @{username}")
            return api_result

        # Kleine Pause zwischen Anfragen
        time.sleep(random.uniform(0.5, 1.0))

        # Methode 2: Normale HTML-Seite mit SharedData
        html_result = self._try_html_with_shared_data(username)
        if html_result.get('success'):
            logger.info(f"Method 2 (HTML SharedData) successful for @{username}")
            return html_result

        time.sleep(random.uniform(0.5, 1.0))

        # Methode 3: Meta-Tags als letzter Fallback
        meta_result = self._try_meta_tags_fallback(username)
        if meta_result.get('success'):
            logger.info(f"Method 3 (Meta Tags) successful for @{username}")
            return meta_result

        # Alle Methoden fehlgeschlagen
        result['error'] = "Profil konnte nicht geladen werden. Instagram blockiert möglicherweise die Anfrage."
        logger.warning(f"All methods failed for @{username}")
        return result

    def _try_web_profile_api(self, username: str) -> Dict[str, Any]:
        """
        Versucht die Instagram Web Profile Info API.
        Diese gibt strukturierte JSON-Daten zurück.
        """
        result = self._get_empty_result(username)

        try:
            url = self.MOBILE_URL_TEMPLATE.format(username=username)
            headers = self._get_api_headers()

            # Erst Instagram-Startseite besuchen für Cookies
            self.session.get(
                'https://www.instagram.com/',
                headers=self._get_desktop_headers(),
                timeout=10
            )

            response = self.session.get(url, headers=headers, timeout=self.TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                user_data = data.get('data', {}).get('user', {})

                if user_data:
                    result['success'] = True
                    result['name'] = user_data.get('full_name') or username
                    result['bio'] = user_data.get('biography')
                    result['website'] = user_data.get('external_url')
                    result['follower_count'] = user_data.get('edge_followed_by', {}).get('count', 0)
                    result['profile_picture_url'] = user_data.get('profile_pic_url_hd') or user_data.get('profile_pic_url')

                    # Website aus Bio extrahieren falls nicht vorhanden
                    if not result['website'] and result['bio']:
                        result['website'] = self._extract_website_from_text(result['bio'])

                    return result

            elif response.status_code == 404:
                result['error'] = f"Profil @{username} nicht gefunden"
                return result

        except requests.RequestException as e:
            logger.debug(f"Web Profile API failed for @{username}: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Web Profile API JSON parse failed for @{username}: {e}")

        return result

    def _try_html_with_shared_data(self, username: str) -> Dict[str, Any]:
        """
        Lädt die Profilseite und sucht nach eingebetteten JSON-Daten.
        Instagram speichert Profildaten oft in window._sharedData oder __additionalDataLoaded.
        """
        result = self._get_empty_result(username)

        try:
            url = self.PROFILE_URL_TEMPLATE.format(username=username)
            headers = self._get_desktop_headers()

            response = self.session.get(url, headers=headers, timeout=self.TIMEOUT)

            if response.status_code == 404:
                result['error'] = f"Profil @{username} nicht gefunden"
                return result

            if response.status_code != 200:
                return result

            html = response.text

            # Methode A: window._sharedData
            shared_data_match = re.search(
                r'window\._sharedData\s*=\s*({.+?});</script>',
                html,
                re.DOTALL
            )
            if shared_data_match:
                try:
                    shared_data = json.loads(shared_data_match.group(1))
                    user_data = (
                        shared_data.get('entry_data', {})
                        .get('ProfilePage', [{}])[0]
                        .get('graphql', {})
                        .get('user', {})
                    )
                    if user_data:
                        result = self._parse_user_data(user_data, result)
                        if result.get('name') or result.get('bio'):
                            result['success'] = True
                            return result
                except (json.JSONDecodeError, IndexError, KeyError):
                    pass

            # Methode B: __additionalDataLoaded
            additional_data_match = re.search(
                r'__additionalDataLoaded\s*\(\s*[\'"].*?[\'"]\s*,\s*({.+?})\s*\)',
                html,
                re.DOTALL
            )
            if additional_data_match:
                try:
                    additional_data = json.loads(additional_data_match.group(1))
                    user_data = additional_data.get('graphql', {}).get('user', {})
                    if not user_data:
                        user_data = additional_data.get('user', {})
                    if user_data:
                        result = self._parse_user_data(user_data, result)
                        if result.get('name') or result.get('bio'):
                            result['success'] = True
                            return result
                except (json.JSONDecodeError, KeyError):
                    pass

            # Methode C: Suche nach JSON in script-Tags
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script', type='application/json'):
                if script.string:
                    try:
                        data = json.loads(script.string)
                        user_data = self._find_user_in_json(data)
                        if user_data:
                            result = self._parse_user_data(user_data, result)
                            if result.get('name') or result.get('bio'):
                                result['success'] = True
                                return result
                    except (json.JSONDecodeError, TypeError):
                        continue

        except requests.RequestException as e:
            logger.debug(f"HTML SharedData failed for @{username}: {e}")

        return result

    def _try_meta_tags_fallback(self, username: str) -> Dict[str, Any]:
        """
        Letzter Fallback: Extrahiert was möglich ist aus Meta-Tags.
        """
        result = self._get_empty_result(username)

        try:
            url = self.PROFILE_URL_TEMPLATE.format(username=username)
            headers = self._get_desktop_headers()

            response = self.session.get(url, headers=headers, timeout=self.TIMEOUT)

            if response.status_code == 404:
                result['error'] = f"Profil @{username} nicht gefunden"
                return result

            if response.status_code != 200:
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Title Tag
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text()
                # Format: "Name (@username) • Instagram photos and videos"
                name_match = re.match(r'^(.+?)\s*\(@', title_text)
                if name_match:
                    result['name'] = name_match.group(1).strip()

            # Description Meta-Tag
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag and desc_tag.get('content'):
                desc = desc_tag['content']

                # Follower extrahieren
                follower_match = re.search(r'([\d,\.]+[KMk]?)\s*Follower', desc, re.IGNORECASE)
                if follower_match:
                    result['follower_count'] = self._parse_follower_count(follower_match.group(1))

                # Bio nach "-" oder ":"
                bio_match = re.search(r'[-–:]\s*["\"]?(.+?)(?:["\"]?\s*$|\s*„)', desc)
                if bio_match:
                    bio_text = bio_match.group(1).strip()
                    # Entferne "See Instagram photos..." am Ende
                    bio_text = re.sub(r'\s*See Instagram.*$', '', bio_text, flags=re.IGNORECASE)
                    if bio_text and len(bio_text) > 5:
                        result['bio'] = bio_text

            # OG-Tags
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                result['profile_picture_url'] = og_image['content']

            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content') and not result['name']:
                title = og_title['content']
                name_match = re.match(r'^(.+?)\s*\(@', title)
                if name_match:
                    result['name'] = name_match.group(1).strip()

            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content') and not result['bio']:
                desc = og_desc['content']
                parts = desc.split(' - ')
                if len(parts) > 1:
                    bio_text = ' - '.join(parts[1:]).strip()
                    bio_text = re.sub(r'\s*See Instagram.*$', '', bio_text, flags=re.IGNORECASE)
                    if bio_text and len(bio_text) > 5:
                        result['bio'] = bio_text

            # Website aus Bio extrahieren
            if not result['website'] and result['bio']:
                result['website'] = self._extract_website_from_text(result['bio'])

            # Mindestens Name oder Bio gefunden
            if result['name'] or result['bio']:
                result['success'] = True

        except requests.RequestException as e:
            logger.debug(f"Meta tags fallback failed for @{username}: {e}")

        return result

    def _get_empty_result(self, username: str) -> Dict[str, Any]:
        """Erstellt ein leeres Result-Dictionary."""
        return {
            'success': False,
            'username': username,
            'name': None,
            'bio': None,
            'website': None,
            'follower_count': 0,
            'profile_picture_url': None,
            'error': None,
        }

    def _parse_user_data(self, user_data: Dict, result: Dict) -> Dict:
        """Parst User-Daten aus verschiedenen JSON-Strukturen."""
        result['name'] = user_data.get('full_name') or result.get('name')
        result['bio'] = user_data.get('biography') or result.get('bio')
        result['website'] = user_data.get('external_url') or result.get('website')

        # Follower Count aus verschiedenen Strukturen
        if 'edge_followed_by' in user_data:
            result['follower_count'] = user_data['edge_followed_by'].get('count', 0)
        elif 'follower_count' in user_data:
            result['follower_count'] = user_data['follower_count']

        # Profilbild
        result['profile_picture_url'] = (
            user_data.get('profile_pic_url_hd') or
            user_data.get('profile_pic_url') or
            result.get('profile_picture_url')
        )

        # Website aus Bio falls nicht vorhanden
        if not result['website'] and result['bio']:
            result['website'] = self._extract_website_from_text(result['bio'])

        return result

    def _find_user_in_json(self, data: Any, depth: int = 0) -> Optional[Dict]:
        """Sucht rekursiv nach User-Daten in einer JSON-Struktur."""
        if depth > 10:  # Tiefenbegrenzung
            return None

        if isinstance(data, dict):
            # Direkter User-Match
            if 'full_name' in data and 'biography' in data:
                return data
            if 'username' in data and ('full_name' in data or 'edge_followed_by' in data):
                return data

            # Rekursiv suchen
            for key in ['user', 'graphql', 'data']:
                if key in data:
                    result = self._find_user_in_json(data[key], depth + 1)
                    if result:
                        return result

            # Alle Werte durchsuchen
            for value in data.values():
                if isinstance(value, (dict, list)):
                    result = self._find_user_in_json(value, depth + 1)
                    if result:
                        return result

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    result = self._find_user_in_json(item, depth + 1)
                    if result:
                        return result

        return None

    def _parse_follower_count(self, count_str: str) -> int:
        """Parst Follower-Anzahl aus verschiedenen Formaten."""
        count_str = count_str.strip().upper()
        count_str = count_str.replace(',', '').replace('.', '')

        multiplier = 1
        if count_str.endswith('K'):
            multiplier = 1000
            count_str = count_str[:-1]
        elif count_str.endswith('M'):
            multiplier = 1000000
            count_str = count_str[:-1]

        try:
            return int(float(count_str) * multiplier)
        except ValueError:
            return 0

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
            if not any(social in domain for social in ['instagram.com', 'facebook.com', 'fb.com']):
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

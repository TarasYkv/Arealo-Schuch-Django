"""
Image Searcher für LoomMarket.
Sucht Logos und Produktbilder über Google Custom Search API.
Fallback auf DuckDuckGo wenn kein API-Key konfiguriert.
"""
import os
import io
import uuid
import logging
import requests
from PIL import Image
from typing import List, Dict, Any, Optional
from django.core.files.base import ContentFile
from django.conf import settings

logger = logging.getLogger(__name__)


class ImageSearcher:
    """
    Sucht Bilder über Google Custom Search API oder DuckDuckGo.
    Google wird bevorzugt (zuverlässiger, kein Rate-Limit bei 100/Tag).
    """

    # User-Agent für Requests
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # Google Custom Search API
    GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"

    # Timeout für Requests
    TIMEOUT = 15

    # Maximale Bildgröße in Bytes (5 MB)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    # Mindestgröße für Bilder
    MIN_WIDTH = 100
    MIN_HEIGHT = 100

    def __init__(self, google_api_key: str = None, google_cx: str = None):
        """
        Initialisiert den ImageSearcher.

        Args:
            google_api_key: Google Custom Search API Key (optional, nutzt settings wenn nicht angegeben)
            google_cx: Google Custom Search Engine ID (optional, nutzt settings wenn nicht angegeben)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        })

        # Google API Credentials
        self.google_api_key = google_api_key or getattr(settings, 'GOOGLE_API_KEY', None)
        self.google_cx = google_cx or getattr(settings, 'GOOGLE_SEARCH_CX', None)

        # Prüfe ob Google API verfügbar
        self.use_google = bool(self.google_api_key and self.google_cx)

        if self.use_google:
            logger.info("ImageSearcher initialized with Google Custom Search API")
        else:
            logger.info("ImageSearcher initialized with DuckDuckGo fallback (no Google API key)")

    def search_images(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = 'all'
    ) -> List[Dict[str, Any]]:
        """
        Sucht Bilder zu einer Suchanfrage.

        Args:
            query: Suchbegriff
            max_results: Maximale Anzahl Ergebnisse
            search_type: 'all', 'logo', 'product'

        Returns:
            Liste mit Bildinformationen
        """
        # Suchtyp-spezifische Modifikationen
        if search_type == 'logo':
            query = f"{query} logo"
        elif search_type == 'product':
            query = f"{query} produkt"

        # Google API verwenden wenn verfügbar
        if self.use_google:
            results = self._search_google(query, max_results, search_type)
            if results:
                return results
            logger.warning("Google search failed, trying DuckDuckGo fallback")

        # DuckDuckGo Fallback
        return self._search_duckduckgo(query, max_results, search_type)

    def _search_google(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Sucht Bilder über Google Custom Search API.
        """
        results = []

        try:
            logger.info(f"Google Image Search: {query}")

            # Google API Params
            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': query,
                'searchType': 'image',
                'num': min(max_results, 10),  # Max 10 pro Request
                'safe': 'active',
                'imgType': 'photo',
            }

            # Für Logos: PNG und clipart bevorzugen
            if search_type == 'logo':
                params['imgType'] = 'clipart'
                params['fileType'] = 'png'

            response = self.session.get(
                self.GOOGLE_API_URL,
                params=params,
                timeout=self.TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])

                for item in items:
                    if len(results) >= max_results:
                        break

                    image_info = item.get('image', {})

                    result = {
                        'url': item.get('link'),
                        'thumbnail': image_info.get('thumbnailLink'),
                        'title': item.get('title', ''),
                        'source': item.get('displayLink', ''),
                        'width': image_info.get('width', 0),
                        'height': image_info.get('height', 0),
                    }

                    if self._validate_image_result(result, search_type):
                        results.append(result)

                logger.info(f"Google found {len(results)} images for: {query}")

            elif response.status_code == 403:
                logger.error("Google API quota exceeded or invalid key")
            else:
                logger.warning(f"Google API error: {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Google API request failed: {e}")
        except Exception as e:
            logger.exception(f"Google search error: {e}")

        return results

    def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Sucht Bilder über DuckDuckGo (Fallback).
        """
        results = []

        try:
            from duckduckgo_search import DDGS

            logger.info(f"DuckDuckGo Image Search: {query}")

            with DDGS() as ddgs:
                ddgs_results = list(ddgs.images(
                    keywords=query,
                    region="de-de",
                    safesearch="moderate",
                    max_results=max_results * 2  # Mehr holen für Filterung
                ))

                for img in ddgs_results:
                    if len(results) >= max_results:
                        break

                    result = {
                        'url': img.get('image'),
                        'thumbnail': img.get('thumbnail'),
                        'title': img.get('title', ''),
                        'source': img.get('url', ''),
                        'width': img.get('width', 0),
                        'height': img.get('height', 0),
                    }

                    if self._validate_image_result(result, search_type):
                        results.append(result)

            logger.info(f"DuckDuckGo found {len(results)} images for: {query}")

        except ImportError:
            logger.error("duckduckgo_search not installed")
        except Exception as e:
            # Rate limit oder anderer Fehler
            if 'Ratelimit' in str(e):
                logger.warning("DuckDuckGo rate limit reached")
            else:
                logger.exception(f"DuckDuckGo search error: {e}")

        return results

    def _validate_image_result(self, result: Dict, search_type: str) -> bool:
        """Validiert ein Suchergebnis."""
        url = result.get('url', '')

        if not url:
            return False

        # Blockierte Domains
        blocked_domains = [
            'facebook.com', 'fbcdn.net',
            'instagram.com', 'cdninstagram.com',
            'pinterest.com', 'pinimg.com',
        ]

        for domain in blocked_domains:
            if domain in url:
                return False

        # Größenprüfung (wenn verfügbar)
        width = result.get('width', 0)
        height = result.get('height', 0)

        if width > 0 and height > 0:
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                return False

        # Logo-spezifische Checks
        if search_type == 'logo':
            is_square = abs(width - height) < 100 if width > 0 and height > 0 else False
            is_png = url.lower().endswith('.png')

            # Mindestens eines der Kriterien für Logos
            if not (is_square or is_png or 'logo' in url.lower()):
                return False

        return True

    def search_logos(self, company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht speziell nach Logos.
        """
        return self.search_images(company_name, max_results, search_type='logo')

    def search_products(self, company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht nach Produktbildern.
        """
        return self.search_images(company_name, max_results, search_type='product')

    def download_image(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Lädt ein Bild herunter und gibt es als ContentFile zurück.
        """
        try:
            logger.info(f"Downloading image: {url[:100]}...")

            response = self.session.get(url, timeout=self.TIMEOUT, stream=True)
            response.raise_for_status()

            # Größe prüfen
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.MAX_IMAGE_SIZE:
                logger.warning(f"Image too large: {content_length} bytes")
                return None

            # Bild laden
            image_data = response.content

            if len(image_data) > self.MAX_IMAGE_SIZE:
                logger.warning(f"Downloaded image too large: {len(image_data)} bytes")
                return None

            # Mit PIL validieren
            try:
                img = Image.open(io.BytesIO(image_data))
                width, height = img.size

                if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                    logger.warning(f"Image too small: {width}x{height}")
                    return None

                # Format bestimmen
                img_format = img.format or 'PNG'
                if img_format.upper() == 'JPEG':
                    ext = 'jpg'
                else:
                    ext = img_format.lower()

            except Exception as e:
                logger.warning(f"Invalid image: {e}")
                return None

            # Dateiname generieren
            filename = f"{uuid.uuid4().hex[:12]}.{ext}"

            return {
                'image': ContentFile(image_data, name=filename),
                'width': width,
                'height': height,
                'file_size': len(image_data),
                'source_url': url,
            }

        except requests.Timeout:
            logger.warning(f"Timeout downloading: {url[:50]}...")
        except requests.RequestException as e:
            logger.warning(f"Request error: {e}")
        except Exception as e:
            logger.exception(f"Error downloading image: {e}")

        return None

    def search_and_download(
        self,
        company_name: str,
        max_logos: int = 3,
        max_products: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Sucht und lädt Logos und Produktbilder herunter.
        """
        results = {
            'logos': [],
            'products': [],
        }

        # Logos suchen und herunterladen
        logo_results = self.search_logos(company_name, max_logos * 2)
        for logo_info in logo_results:
            if len(results['logos']) >= max_logos:
                break

            downloaded = self.download_image(logo_info['url'])
            if downloaded:
                downloaded['is_logo'] = True
                downloaded['title'] = logo_info.get('title', '')
                results['logos'].append(downloaded)

        # Produktbilder suchen und herunterladen
        product_results = self.search_products(company_name, max_products * 2)
        for product_info in product_results:
            if len(results['products']) >= max_products:
                break

            # Duplikate vermeiden (gleiche URL)
            if any(p.get('source_url') == product_info['url'] for p in results['logos']):
                continue

            downloaded = self.download_image(product_info['url'])
            if downloaded:
                downloaded['is_logo'] = False
                downloaded['title'] = product_info.get('title', '')
                results['products'].append(downloaded)

        logger.info(
            f"Downloaded {len(results['logos'])} logos and "
            f"{len(results['products'])} products for: {company_name}"
        )

        return results

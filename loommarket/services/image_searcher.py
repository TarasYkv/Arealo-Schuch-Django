"""
Image Searcher für LoomMarket.
Sucht Logos und Produktbilder über Bing Image Search API.
Fallback auf DuckDuckGo wenn kein API-Key konfiguriert.
"""
import io
import uuid
import logging
import requests
from PIL import Image
from typing import List, Dict, Any, Optional
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class ImageSearcher:
    """
    Sucht Bilder über Bing Image Search API oder DuckDuckGo.
    Bing wird bevorzugt (1000 kostenlose Anfragen/Monat).
    """

    # User-Agent für Requests
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # Bing Image Search API
    BING_API_URL = "https://api.bing.microsoft.com/v7.0/images/search"

    # Timeout für Requests
    TIMEOUT = 15

    # Maximale Bildgröße in Bytes (5 MB)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    # Mindestgröße für Bilder
    MIN_WIDTH = 100
    MIN_HEIGHT = 100

    def __init__(self, bing_api_key: str = None):
        """
        Initialisiert den ImageSearcher.

        Args:
            bing_api_key: Bing Image Search API Key (optional)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        })

        # Bing API Key
        self.bing_api_key = bing_api_key

        # Prüfe ob Bing API verfügbar
        self.use_bing = bool(self.bing_api_key)

        if self.use_bing:
            logger.info("ImageSearcher initialized with Bing Image Search API")
        else:
            logger.info("ImageSearcher initialized with DuckDuckGo fallback (no Bing API key)")

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

        # Bing API verwenden wenn verfügbar
        if self.use_bing:
            results = self._search_bing(query, max_results, search_type)
            if results:
                return results
            logger.warning("Bing search failed, trying DuckDuckGo fallback")

        # DuckDuckGo Fallback
        return self._search_duckduckgo(query, max_results, search_type)

    def _search_bing(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Sucht Bilder über Bing Image Search API.
        """
        results = []

        try:
            logger.info(f"Bing Image Search: {query}")

            headers = {
                'Ocp-Apim-Subscription-Key': self.bing_api_key,
            }

            params = {
                'q': query,
                'count': min(max_results * 2, 50),  # Mehr holen für Filterung
                'mkt': 'de-DE',
                'safeSearch': 'Moderate',
            }

            # Für Logos: PNG und transparente Bilder bevorzugen
            if search_type == 'logo':
                params['imageType'] = 'Clipart'

            response = self.session.get(
                self.BING_API_URL,
                headers=headers,
                params=params,
                timeout=self.TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get('value', [])

                for item in items:
                    if len(results) >= max_results:
                        break

                    result = {
                        'url': item.get('contentUrl'),
                        'thumbnail': item.get('thumbnailUrl'),
                        'title': item.get('name', ''),
                        'source': item.get('hostPageDisplayUrl', ''),
                        'width': item.get('width', 0),
                        'height': item.get('height', 0),
                    }

                    if self._validate_image_result(result, search_type):
                        results.append(result)

                logger.info(f"Bing found {len(results)} images for: {query}")

            elif response.status_code == 401:
                logger.error("Bing API: Invalid subscription key")
            elif response.status_code == 403:
                logger.error("Bing API: Quota exceeded or access denied")
            else:
                logger.warning(f"Bing API error: {response.status_code} - {response.text[:200]}")

        except requests.RequestException as e:
            logger.error(f"Bing API request failed: {e}")
        except Exception as e:
            logger.exception(f"Bing search error: {e}")

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

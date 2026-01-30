"""
Image Searcher für LoomMarket.
Sucht Logos und Produktbilder über Bildersuche.
"""
import os
import re
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
    Sucht Bilder über DuckDuckGo Images.
    Fokus auf Logos und Produktbilder.
    """

    # User-Agent für Requests
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # DuckDuckGo Image Search URL
    DDG_URL = "https://duckduckgo.com/"
    DDG_IMAGE_URL = "https://duckduckgo.com/i.js"

    # Timeout für Requests
    TIMEOUT = 15

    # Maximale Bildgröße in Bytes (5 MB)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    # Mindestgröße für Bilder
    MIN_WIDTH = 100
    MIN_HEIGHT = 100

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        })

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
        try:
            # DuckDuckGo-Search verwenden
            from duckduckgo_search import DDGS

            results = []

            with DDGS() as ddgs:
                # Suchtyp-spezifische Modifikationen
                if search_type == 'logo':
                    query = f"{query} logo transparent png"
                elif search_type == 'product':
                    query = f"{query} produkt"

                logger.info(f"Searching images: {query}")

                # Bilder suchen
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

                    # Basis-Validierung
                    if self._validate_image_result(result, search_type):
                        results.append(result)

            logger.info(f"Found {len(results)} images for: {query}")
            return results

        except ImportError:
            logger.error("duckduckgo_search not installed")
            return []
        except Exception as e:
            logger.exception(f"Error searching images: {e}")
            return []

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
            # Bevorzuge quadratische Bilder oder PNG
            is_square = abs(width - height) < 50 if width > 0 and height > 0 else False
            is_png = url.lower().endswith('.png')

            # Mindestens eines der Kriterien
            if not (is_square or is_png or 'logo' in url.lower()):
                return False

        return True

    def search_logos(self, company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht speziell nach Logos.

        Args:
            company_name: Firmenname
            max_results: Maximale Anzahl

        Returns:
            Liste mit Logo-Bildinformationen
        """
        return self.search_images(company_name, max_results, search_type='logo')

    def search_products(self, company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht nach Produktbildern.

        Args:
            company_name: Firmenname
            max_results: Maximale Anzahl

        Returns:
            Liste mit Produktbildinformationen
        """
        return self.search_images(company_name, max_results, search_type='product')

    def download_image(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Lädt ein Bild herunter und gibt es als ContentFile zurück.

        Args:
            url: Bild-URL

        Returns:
            Dict mit image (ContentFile), width, height, file_size oder None
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

        Args:
            company_name: Firmenname
            max_logos: Maximale Anzahl Logos
            max_products: Maximale Anzahl Produktbilder

        Returns:
            Dict mit 'logos' und 'products' Listen
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

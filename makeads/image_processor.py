import re
import requests
import logging
import mimetypes
import hashlib
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import tempfile
import os

logger = logging.getLogger(__name__)


class ImageURLProcessor:
    """
    Verarbeitet URLs und erkennt/lädt Bilder automatisch herunter
    """
    
    # Unterstützte Bildformate
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    SUPPORTED_MIME_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/webp', 'image/bmp', 'image/tiff'
    }
    
    # URL Pattern für Bild-URLs
    IMAGE_URL_PATTERN = re.compile(
        r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|tiff)(?:\?[^\s]*)?',
        re.IGNORECASE
    )
    
    def __init__(self, max_file_size_mb: int = 10, timeout: int = 30):
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        self.timeout = timeout
        
    def extract_image_urls(self, text: str) -> List[str]:
        """
        Extrahiert alle Bild-URLs aus einem Text
        """
        if not text:
            return []
            
        urls = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Direkte URL-Erkennung
            if self._is_potential_image_url(line):
                urls.append(line)
            else:
                # Pattern-basierte Extraktion für URLs in Text
                found_urls = self.IMAGE_URL_PATTERN.findall(line)
                urls.extend(found_urls)
        
        return list(set(urls))  # Remove duplicates
    
    def _is_potential_image_url(self, url: str) -> bool:
        """
        Überprüft ob eine URL potentiell ein Bild ist
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
                
            # Check file extension
            path_lower = parsed.path.lower()
            for ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                if ext in path_lower:
                    return True
                    
            return False
        except Exception:
            return False
    
    def download_image(self, url: str, filename_prefix: str = "reference") -> Tuple[Optional[ContentFile], Dict]:
        """
        Lädt ein Bild von einer URL herunter
        
        Returns:
            Tuple[Optional[ContentFile], Dict]: (file_content, metadata)
        """
        metadata = {
            'url': url,
            'success': False,
            'error': None,
            'size': 0,
            'content_type': None,
            'filename': None
        }
        
        try:
            logger.info(f"Downloading image from URL: {url}")
            
            # Request mit Headers um als echter Browser zu erscheinen
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Content-Type überprüfen
            content_type = response.headers.get('content-type', '').lower()
            if not any(mime in content_type for mime in self.SUPPORTED_MIME_TYPES):
                metadata['error'] = f'Unsupported content type: {content_type}'
                logger.warning(f"Unsupported content type {content_type} for URL: {url}")
                return None, metadata
            
            # Content-Length prüfen
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_file_size:
                metadata['error'] = f'File too large: {content_length} bytes'
                logger.warning(f"File too large ({content_length} bytes) for URL: {url}")
                return None, metadata
            
            # Bild-Daten lesen
            image_data = BytesIO()
            total_size = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > self.max_file_size:
                        metadata['error'] = f'File too large during download: {total_size} bytes'
                        logger.warning(f"File became too large during download for URL: {url}")
                        return None, metadata
                    image_data.write(chunk)
            
            image_data.seek(0)
            
            # Dateiname generieren
            parsed_url = urlparse(url)
            original_filename = os.path.basename(parsed_url.path)
            if not original_filename or '.' not in original_filename:
                # Generate filename from content type
                ext_map = {
                    'image/jpeg': '.jpg',
                    'image/jpg': '.jpg', 
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/webp': '.webp',
                    'image/bmp': '.bmp',
                    'image/tiff': '.tiff'
                }
                ext = ext_map.get(content_type, '.jpg')
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                original_filename = f"{filename_prefix}_{url_hash}{ext}"
            
            # Bild validieren mit PIL
            try:
                image_data.seek(0)
                with Image.open(image_data) as img:
                    img.verify()  # Verify it's a valid image
                image_data.seek(0)
            except Exception as e:
                metadata['error'] = f'Invalid image file: {str(e)}'
                logger.warning(f"Invalid image file for URL {url}: {str(e)}")
                return None, metadata
            
            # ContentFile erstellen
            content_file = ContentFile(image_data.read(), name=original_filename)
            
            # Metadata aktualisieren
            metadata.update({
                'success': True,
                'size': total_size,
                'content_type': content_type,
                'filename': original_filename
            })
            
            logger.info(f"Successfully downloaded image: {original_filename} ({total_size} bytes)")
            return content_file, metadata
            
        except requests.exceptions.Timeout as e:
            metadata['error'] = f'Request timeout after {self.timeout}s'
            logger.error(f"Timeout downloading image from {url}: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            metadata['error'] = f'Connection failed: {str(e)}'
            logger.error(f"Connection error downloading image from {url}: {str(e)}")
        except requests.exceptions.HTTPError as e:
            metadata['error'] = f'HTTP error {e.response.status_code}: {str(e)}'
            logger.error(f"HTTP error downloading image from {url}: {str(e)}")
        except requests.RequestException as e:
            metadata['error'] = f'Request failed: {str(e)}'
            logger.error(f"Request failed downloading image from {url}: {str(e)}")
        except IOError as e:
            metadata['error'] = f'File I/O error: {str(e)}'
            logger.error(f"I/O error processing image from {url}: {str(e)}")
        except Exception as e:
            metadata['error'] = f'Unexpected error: {str(e)}'
            logger.error(f"Unexpected error downloading image from {url}: {str(e)}", exc_info=True)
            
        return None, metadata


class ReferenceImageAnalyzer:
    """
    Analysiert Referenzbilder mit GPT-4 Vision API
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            
    def analyze_image(self, image_file, original_filename: str = None) -> Dict:
        """
        Analysiert ein Bild und extrahiert Stil, Farben, Layout-Informationen
        
        Args:
            image_file: Django ImageField oder file path
            original_filename: Original filename for context
            
        Returns:
            Dict with analysis results
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API key not configured',
                'description': 'Referenzbild (nicht analysiert)',
                'style_elements': {},
                'colors': [],
                'layout_description': '',
                'recommendations': []
            }
            
        try:
            logger.info(f"Analyzing image: {original_filename or 'unnamed'}")
            
            # Bild zu base64 konvertieren
            base64_image = self._image_to_base64(image_file)
            if not base64_image:
                return {
                    'success': False,
                    'error': 'Could not convert image to base64',
                    'description': 'Referenzbild (Konvertierungsfehler)',
                    'style_elements': {},
                    'colors': [],
                    'layout_description': '',
                    'recommendations': []
                }
            
            # GPT-4 Vision Prompt
            prompt = """
            Analysiere dieses Referenzbild für Werbe-/Marketing-Creative-Erstellung. 
            
            Bitte analysiere folgende Aspekte:
            
            1. **Visuelle Stilrichtung**: Modern, klassisch, minimal, verspielt, elegant, etc.
            2. **Farbpalette**: Hauptfarben, Farbharmonie, Stimmung der Farben
            3. **Typografie**: Schriftarten-Stil, Textplatzierung, Hierarchie (falls Text vorhanden)
            4. **Layout & Komposition**: Anordnung der Elemente, Weißraum, Balance
            5. **Designelemente**: Formen, Linien, Texturen, Effekte
            6. **Zielgruppe**: Für welche Zielgruppe scheint dieses Design geeignet
            7. **Stimmung/Emotion**: Welche Gefühle/Stimmung vermittelt das Bild
            
            Antworte im JSON-Format:
            {
                "description": "Kurze, prägnante Beschreibung des Bildes (1-2 Sätze)",
                "style_elements": {
                    "overall_style": "z.B. modern, minimalistisch, vintage",
                    "mood": "z.B. professionell, verspielt, elegant", 
                    "target_audience": "z.B. junge Erwachsene, Business-Professionals"
                },
                "colors": [
                    {"color": "#HEX-CODE", "description": "Hauptfarbe - warm/kalt/neutral"},
                    {"color": "#HEX-CODE", "description": "Akzentfarbe - energisch/ruhig"}
                ],
                "layout_description": "Beschreibung der Komposition und Anordnung",
                "recommendations": [
                    "Empfehlung 1 für Creative-Erstellung basierend auf diesem Stil",
                    "Empfehlung 2 für Farbverwendung",
                    "Empfehlung 3 für Layout/Komposition"
                ]
            }
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            # Response verarbeiten
            content = response.choices[0].message.content
            logger.info(f"GPT-4 Vision response: {content[:200]}...")
            
            # JSON parsing
            try:
                import json
                analysis = json.loads(content)
                analysis['success'] = True
                analysis['raw_response'] = content
                
                logger.info(f"Successfully analyzed image: {analysis.get('description', 'No description')}")
                return analysis
                
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse JSON response: {str(e)}")
                # Fallback with raw content
                return {
                    'success': True,
                    'description': content[:200] if content else 'Referenzbild analysiert',
                    'style_elements': {'overall_style': 'unbekannt'},
                    'colors': [],
                    'layout_description': content[:500] if content else '',
                    'recommendations': [content] if content else [],
                    'raw_response': content,
                    'parse_error': str(e)
                }
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific OpenAI API errors
            if 'billing_hard_limit_reached' in error_msg:
                error_msg = 'OpenAI Billing-Limit erreicht'
            elif 'insufficient_quota' in error_msg:
                error_msg = 'OpenAI Guthaben erschöpft'
            elif 'rate_limit_exceeded' in error_msg:
                error_msg = 'OpenAI Rate-Limit erreicht - bitte später versuchen'
            elif 'invalid_api_key' in error_msg:
                error_msg = 'Ungültiger OpenAI API-Key'
            elif 'model_not_found' in error_msg:
                error_msg = 'GPT-4 Vision Modell nicht verfügbar'
            elif 'image_too_large' in error_msg:
                error_msg = 'Bild zu groß für Analyse'
            
            logger.error(f"Error analyzing image: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'description': f'Referenzbild - {original_filename or "unbekannt"}',
                'style_elements': {},
                'colors': [],
                'layout_description': '',
                'recommendations': []
            }
    
    def _image_to_base64(self, image_file) -> Optional[str]:
        """
        Konvertiert ein Bild zu base64 für GPT-4 Vision
        """
        try:
            # Handle different input types
            if hasattr(image_file, 'read'):
                # File-like object
                image_file.seek(0)
                image_data = image_file.read()
                image_file.seek(0)
            elif hasattr(image_file, 'path'):
                # Django ImageField
                with open(image_file.path, 'rb') as f:
                    image_data = f.read()
            elif isinstance(image_file, str):
                # File path
                with open(image_file, 'rb') as f:
                    image_data = f.read()
            else:
                logger.error(f"Unknown image file type: {type(image_file)}")
                return None
            
            # Resize if too large (GPT-4 Vision has size limits)
            image_data = self._resize_image_if_needed(image_data)
            
            # Convert to base64
            base64_string = base64.b64encode(image_data).decode('utf-8')
            return base64_string
            
        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            return None
    
    def _resize_image_if_needed(self, image_data: bytes, max_size: int = 2000) -> bytes:
        """
        Resize image if it's too large for GPT-4 Vision API
        """
        try:
            # Check if resize is needed
            with Image.open(BytesIO(image_data)) as img:
                width, height = img.size
                
                if width <= max_size and height <= max_size:
                    return image_data
                
                # Calculate new size maintaining aspect ratio
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                # Resize image
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save to bytes
                output = BytesIO()
                # Preserve format, default to JPEG if unknown
                format_name = img.format or 'JPEG'
                if format_name == 'GIF':
                    format_name = 'PNG'  # GIF not always supported for saving
                    
                img.save(output, format=format_name, quality=85, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            logger.warning(f"Could not resize image: {str(e)}, using original")
            return image_data


class ReferenceManager:
    """
    Kombiniert URL-Processing und Bild-Analyse für vollständige Referenz-Verwaltung
    """
    
    def __init__(self, openai_api_key: str = None):
        self.url_processor = ImageURLProcessor()
        self.image_analyzer = ReferenceImageAnalyzer(openai_api_key)
        
    def process_web_links(self, web_links_text: str, campaign) -> List[Dict]:
        """
        Verarbeitet Web-Links und extrahiert/analysiert Bilder
        
        Returns:
            List[Dict]: Liste mit Verarbeitungsresultaten
        """
        results = []
        
        if not web_links_text:
            return results
            
        # Extract image URLs
        image_urls = self.url_processor.extract_image_urls(web_links_text)
        
        for url in image_urls:
            result = {
                'url': url,
                'type': 'image_url',
                'processed': False,
                'reference_image': None,
                'analysis': None,
                'error': None
            }
            
            try:
                # Download image
                content_file, download_metadata = self.url_processor.download_image(url)
                
                if content_file and download_metadata['success']:
                    # Create ReferenceImage object
                    from .models import ReferenceImage
                    
                    reference_image = ReferenceImage.objects.create(
                        campaign=campaign,
                        image=content_file,
                        description=f"Auto-downloaded from: {url}"
                    )
                    
                    # Analyze image
                    analysis = self.image_analyzer.analyze_image(
                        reference_image.image, 
                        download_metadata['filename']
                    )
                    
                    # Update description with AI analysis
                    if analysis['success'] and analysis.get('description'):
                        reference_image.description = f"{analysis['description']} (von {url})"
                        reference_image.save()
                    
                    result.update({
                        'processed': True,
                        'reference_image': reference_image,
                        'analysis': analysis,
                        'download_metadata': download_metadata
                    })
                    
                    logger.info(f"Successfully processed image URL: {url}")
                    
                else:
                    result['error'] = download_metadata.get('error', 'Download failed')
                    logger.warning(f"Failed to download image from URL {url}: {result['error']}")
                    
            except Exception as e:
                result['error'] = str(e)
                logger.error(f"Error processing image URL {url}: {str(e)}")
            
            results.append(result)
            
        return results
    
    def analyze_existing_images(self, campaign) -> List[Dict]:
        """
        Analysiert bereits vorhandene Referenzbilder
        """
        from .models import ReferenceImage
        
        results = []
        reference_images = ReferenceImage.objects.filter(campaign=campaign)
        
        for ref_image in reference_images:
            try:
                analysis = self.image_analyzer.analyze_image(
                    ref_image.image,
                    ref_image.image.name
                )
                
                # Update description if analysis was successful
                if analysis['success'] and analysis.get('description'):
                    original_desc = ref_image.description or ""
                    if not "analysiert:" in original_desc:
                        ref_image.description = f"{original_desc} | KI-analysiert: {analysis['description']}"
                        ref_image.save()
                
                results.append({
                    'reference_image': ref_image,
                    'analysis': analysis,
                    'updated': analysis['success']
                })
                
            except Exception as e:
                logger.error(f"Error analyzing existing image {ref_image.id}: {str(e)}")
                results.append({
                    'reference_image': ref_image,
                    'analysis': {'success': False, 'error': str(e)},
                    'updated': False
                })
        
        return results
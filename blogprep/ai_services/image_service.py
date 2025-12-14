"""
Image Service für BlogPrep

Verantwortlich für:
- Titelbild generieren
- Abschnittsbilder generieren
- Diagramme als Bilder generieren
"""

import logging
import base64
import requests
import time
from typing import Dict, Optional, Any
from io import BytesIO
from django.core.files.base import ContentFile

# Optionale Imports
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class ImageService:
    """Service für KI-gestützte Bildgenerierung"""

    # Google API Base URL
    GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle pro Provider
    PROVIDER_MODELS = {
        'gemini': {
            'imagen-3.0-generate-002': 'Imagen 3 (Empfohlen)',
            'gemini-2.0-flash-exp': 'Gemini 2.0 Flash',
        },
        'dalle': {
            'dall-e-3': 'DALL-E 3 (Beste Qualität)',
            'dall-e-2': 'DALL-E 2 (Schneller)',
        },
        'ideogram': {
            'V_2A_TURBO': 'Ideogram Turbo',
            'V_2A': 'Ideogram Standard',
        }
    }

    def __init__(self, user, settings=None):
        """
        Initialisiert den Image Service.

        Args:
            user: Django User Objekt mit API-Keys
            settings: Optional BlogPrepSettings Objekt
        """
        self.user = user
        self.settings = settings

        # Provider und Modell aus Settings oder Defaults
        if settings:
            self.provider = settings.image_provider
            self.model = settings.image_model
        else:
            self.provider = 'gemini'
            self.model = 'imagen-3.0-generate-002'

        # Clients initialisieren
        self._init_clients()

    def _init_clients(self):
        """Initialisiert die API-Clients basierend auf Provider"""
        self.openai_client = None
        self.google_api_key = None
        self.ideogram_api_key = None

        if self.provider == 'dalle' and OPENAI_AVAILABLE and self.user.openai_api_key:
            self.openai_client = OpenAI(api_key=self.user.openai_api_key)
        elif self.provider == 'gemini' and self.user.gemini_api_key:
            self.google_api_key = self.user.gemini_api_key
        elif self.provider == 'ideogram' and hasattr(self.user, 'ideogram_api_key'):
            self.ideogram_api_key = self.user.ideogram_api_key

    def generate_title_image(self, keyword: str, blog_summary: str = '') -> Dict:
        """
        Generiert ein Titelbild für den Blogbeitrag.

        Args:
            keyword: Das Hauptkeyword
            blog_summary: Kurze Zusammenfassung des Blog-Inhalts

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_blog_image_prompt(keyword, blog_summary, is_title=True)

        return self._generate_image(prompt, width=1200, height=630)

    def generate_section_image(self, section_text: str, keyword: str) -> Dict:
        """
        Generiert ein Bild für einen Blog-Abschnitt.

        Args:
            section_text: Der Text des Abschnitts (gekürzt)
            keyword: Das Hauptkeyword

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_blog_image_prompt(keyword, section_text[:500], is_title=False)

        return self._generate_image(prompt, width=800, height=600)

    def generate_diagram_image(self, diagram_type: str, diagram_data: Dict, keyword: str) -> Dict:
        """
        Generiert ein Diagramm als Bild.

        Args:
            diagram_type: Art des Diagramms (bar, pie, flow, etc.)
            diagram_data: Daten für das Diagramm
            keyword: Kontext-Keyword

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_diagram_prompt(diagram_type, diagram_data, keyword)

        return self._generate_image(prompt, width=1000, height=700)

    def _create_blog_image_prompt(self, keyword: str, context: str, is_title: bool = False) -> str:
        """Erstellt einen optimierten Prompt für Blog-Bilder"""
        image_type = "Titelbild" if is_title else "illustrierendes Bild"

        prompt = f"""Erstelle ein professionelles {image_type} für einen Blogbeitrag zum Thema "{keyword}".

KONTEXT: {context[:300] if context else 'Informativer Blogbeitrag'}

STIL-ANFORDERUNGEN:
- Professionelles, modernes Design
- Klare, ansprechende Komposition
- Helle, freundliche Farbpalette
- Keine Textüberlagerungen
- Hochwertige, stock-photo-artige Qualität
- Passend für ein Business-Blog

Das Bild soll informativ und einladend wirken, ohne aufdringlich zu sein."""

        return prompt

    def _create_diagram_prompt(self, diagram_type: str, diagram_data: Dict, keyword: str) -> str:
        """Erstellt einen Prompt für Diagramm-Generierung"""
        type_descriptions = {
            'bar': 'Balkendiagramm mit klar lesbaren Balken und Beschriftungen',
            'pie': 'Kreisdiagramm/Tortendiagramm mit deutlichen Segmenten',
            'line': 'Liniendiagramm mit klarem Verlauf',
            'comparison': 'Vergleichsübersicht mit zwei oder mehr Kategorien',
            'flow': 'Flussdiagramm mit Pfeilen und Schritten',
            'timeline': 'Zeitstrahl mit chronologischen Ereignissen'
        }

        diagram_desc = type_descriptions.get(diagram_type, 'informatives Diagramm')
        title = diagram_data.get('title', f'Diagramm zu {keyword}')
        data_points = diagram_data.get('labels', [])

        prompt = f"""Erstelle ein professionelles {diagram_desc} zum Thema "{keyword}".

TITEL: {title}
DATENPUNKTE: {', '.join(str(d) for d in data_points[:5]) if data_points else 'Verschiedene Kategorien'}

STIL-ANFORDERUNGEN:
- Klares, minimalistisches Design
- Gut lesbare Beschriftungen
- Professionelle Farbpalette (Blau-, Grün- oder Erdtöne)
- Weißer oder heller Hintergrund
- Keine 3D-Effekte, flat design bevorzugt
- Business-Blog geeignet

Das Diagramm muss auf den ersten Blick verständlich sein."""

        return prompt

    def _generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> Dict:
        """
        Generiert ein Bild mit dem konfigurierten Provider.

        Returns:
            Dict mit success, image_data (base64), prompt, error
        """
        start_time = time.time()

        try:
            if self.provider == 'dalle' and self.openai_client:
                result = self._generate_with_dalle(prompt, width, height)
            elif self.provider == 'gemini' and self.google_api_key:
                result = self._generate_with_google(prompt, width, height)
            elif self.provider == 'ideogram' and self.ideogram_api_key:
                result = self._generate_with_ideogram(prompt, width, height)
            else:
                return {
                    'success': False,
                    'error': f'API-Key für {self.provider} nicht konfiguriert',
                    'prompt': prompt
                }

            result['prompt'] = prompt
            result['duration'] = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"Image generation error ({self.provider}): {e}")
            return {
                'success': False,
                'error': str(e),
                'prompt': prompt
            }

    def _generate_with_dalle(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit OpenAI DALL-E"""
        # DALL-E 3 Größen
        if width >= 1792 or height >= 1792:
            size = "1792x1024" if width > height else "1024x1792"
        else:
            size = "1024x1024"

        response = self.openai_client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
            response_format="b64_json"
        )

        image_data = response.data[0].b64_json

        return {
            'success': True,
            'image_data': image_data,
            'model_used': self.model
        }

    def _generate_with_google(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit Google Gemini/Imagen"""
        # Aspect Ratio bestimmen
        ratio = width / height
        if ratio > 1.3:
            aspect_ratio = "16:9"
        elif ratio < 0.77:
            aspect_ratio = "9:16"
        elif ratio > 1.1:
            aspect_ratio = "4:3"
        elif ratio < 0.9:
            aspect_ratio = "3:4"
        else:
            aspect_ratio = "1:1"

        # Imagen vs Gemini
        if 'imagen' in self.model:
            return self._generate_with_imagen(prompt, aspect_ratio)
        else:
            return self._generate_with_gemini_native(prompt, aspect_ratio)

    def _generate_with_imagen(self, prompt: str, aspect_ratio: str) -> Dict:
        """Generiert Bild mit Google Imagen"""
        url = f"{self.GOOGLE_BASE_URL}/models/{self.model}:predict"

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": 1,
                "personGeneration": "allow_adult",
                "safetySetting": "block_medium_and_above"
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.google_api_key
        }

        response = requests.post(url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            error_detail = response.json().get('error', {}).get('message', response.text)
            return {
                'success': False,
                'error': f"Imagen API Error: {error_detail}",
                'model_used': self.model
            }

        data = response.json()
        predictions = data.get('predictions', [])

        if predictions and 'bytesBase64Encoded' in predictions[0]:
            return {
                'success': True,
                'image_data': predictions[0]['bytesBase64Encoded'],
                'model_used': self.model
            }

        return {
            'success': False,
            'error': 'Keine Bilddaten in der Antwort',
            'model_used': self.model
        }

    def _generate_with_gemini_native(self, prompt: str, aspect_ratio: str) -> Dict:
        """Generiert Bild mit Gemini Native Image Generation"""
        url = f"{self.GOOGLE_BASE_URL}/models/{self.model}:generateContent"

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.google_api_key
        }

        response = requests.post(url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            error_detail = response.json().get('error', {}).get('message', response.text)
            return {
                'success': False,
                'error': f"Gemini API Error: {error_detail}",
                'model_used': self.model
            }

        data = response.json()

        # Suche nach Bilddaten in der Antwort
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'inlineData' in part:
                    return {
                        'success': True,
                        'image_data': part['inlineData']['data'],
                        'model_used': self.model
                    }

        return {
            'success': False,
            'error': 'Keine Bilddaten in der Gemini-Antwort',
            'model_used': self.model
        }

    def _generate_with_ideogram(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit Ideogram"""
        # Aspect Ratio mapping
        ratio = width / height
        if ratio > 1.3:
            aspect_ratio = "ASPECT_16_9"
        elif ratio < 0.77:
            aspect_ratio = "ASPECT_9_16"
        elif ratio > 1.1:
            aspect_ratio = "ASPECT_4_3"
        elif ratio < 0.9:
            aspect_ratio = "ASPECT_3_4"
        else:
            aspect_ratio = "ASPECT_1_1"

        url = "https://api.ideogram.ai/generate"

        payload = {
            "image_request": {
                "prompt": prompt,
                "model": self.model,
                "aspect_ratio": aspect_ratio,
                "style_type": "REALISTIC"
            }
        }

        headers = {
            "Api-Key": self.ideogram_api_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            return {
                'success': False,
                'error': f"Ideogram API Error: {response.text}",
                'model_used': self.model
            }

        data = response.json()
        images = data.get('data', [])

        if images and 'url' in images[0]:
            # Lade Bild herunter und konvertiere zu base64
            img_response = requests.get(images[0]['url'], timeout=30)
            if img_response.status_code == 200:
                image_data = base64.b64encode(img_response.content).decode('utf-8')
                return {
                    'success': True,
                    'image_data': image_data,
                    'model_used': self.model
                }

        return {
            'success': False,
            'error': 'Keine Bilddaten von Ideogram erhalten',
            'model_used': self.model
        }

    def save_image_to_field(self, image_data: str, field, filename: str) -> bool:
        """
        Speichert Base64-Bilddaten in ein Django ImageField.

        Args:
            image_data: Base64-kodierte Bilddaten
            field: Django ImageField
            filename: Dateiname ohne Extension

        Returns:
            bool: Erfolg
        """
        try:
            # Dekodiere Base64
            image_bytes = base64.b64decode(image_data)

            # Öffne mit PIL um Format zu bestimmen (falls verfügbar)
            if PIL_AVAILABLE:
                img = Image.open(BytesIO(image_bytes))
                img_format = img.format or 'PNG'
                extension = img_format.lower()
            else:
                extension = 'png'

            # Speichere in Field
            full_filename = f"{filename}.{extension}"

            field.save(full_filename, ContentFile(image_bytes), save=False)
            return True

        except Exception as e:
            logger.error(f"Error saving image to field: {e}")
            return False

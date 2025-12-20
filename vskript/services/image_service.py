"""
VSkript Image Service

Generiert Bilder für Videoskripte mit OpenAI DALL-E und Google Gemini Imagen.
"""

import logging
import re
import time
import requests
from io import BytesIO
from typing import Dict, List, Optional
from django.core.files.base import ContentFile

# Optionale Imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class VSkriptImageService:
    """Service für Bild-Generierung"""

    # Stil-Prompts für verschiedene Bildstile
    STYLE_PROMPTS = {
        'realistic': 'photorealistic, highly detailed, professional photography, 8k resolution',
        'cinematic': 'cinematic shot, dramatic lighting, movie scene, film grain, anamorphic lens',
        'anime': 'anime style, japanese animation, vibrant colors, cel shading',
        'cartoon': 'cartoon style, bold outlines, bright colors, comic book art',
        '3d_render': '3D render, octane render, unreal engine, highly detailed 3D model',
        'watercolor': 'watercolor painting, soft edges, artistic, traditional media',
        'oil_painting': 'oil painting, classical art style, rich textures, museum quality',
        'sketch': 'pencil sketch, hand-drawn, artistic sketch, detailed linework',
        'minimalist': 'minimalist design, clean, simple, modern, lots of white space',
        'vintage': 'vintage style, retro aesthetic, 70s colors, film photography',
        'cyberpunk': 'cyberpunk style, neon lights, futuristic, dark atmosphere, sci-fi',
        'fantasy': 'fantasy art, magical, epic, detailed fantasy illustration',
    }

    def __init__(self, user, settings=None):
        """
        Initialisiert den Image Service.

        Args:
            user: Django User Objekt mit API-Keys
            settings: Optional Settings Objekt
        """
        self.user = user
        self.settings = settings
        self._init_clients()

    def _init_clients(self):
        """Initialisiert die API-Clients"""
        self.openai_client = None
        self.gemini_client = None

        # OpenAI Client
        if OPENAI_AVAILABLE:
            api_key = getattr(self.user, 'openai_api_key', None)
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)

        # Gemini Client (google-genai SDK)
        if GENAI_AVAILABLE:
            api_key = getattr(self.user, 'gemini_api_key', None)
            if api_key:
                self.gemini_client = genai.Client(api_key=api_key)

    def _enhance_prompt(self, base_prompt: str, style: str, context: str = '') -> str:
        """Erweitert den Prompt mit Stil-Anweisungen"""
        style_suffix = self.STYLE_PROMPTS.get(style, '')

        enhanced = base_prompt
        if context:
            enhanced = f"{context}: {base_prompt}"
        if style_suffix:
            enhanced = f"{enhanced}, {style_suffix}"

        return enhanced

    def _generate_with_dalle(
        self,
        prompt: str,
        model: str = 'dall-e-3',
        size: str = '1024x1024',
        quality: str = 'standard'
    ) -> Dict:
        """Generiert ein Bild mit DALL-E"""
        if not self.openai_client:
            return {'success': False, 'error': 'OpenAI API-Key nicht konfiguriert'}

        try:
            start_time = time.time()

            # DALL-E 2 unterstützt nur bestimmte Größen
            if model == 'dall-e-2':
                if size not in ['256x256', '512x512', '1024x1024']:
                    size = '1024x1024'
                quality = 'standard'  # DALL-E 2 hat keine quality Option

            response = self.openai_client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality if model == 'dall-e-3' else None,
                n=1
            )

            image_url = response.data[0].url
            duration = time.time() - start_time

            return {
                'success': True,
                'image_url': image_url,
                'revised_prompt': getattr(response.data[0], 'revised_prompt', prompt),
                'model': model,
                'duration': duration
            }

        except Exception as e:
            logger.error(f"DALL-E error: {e}")
            return {'success': False, 'error': str(e)}

    def _generate_with_gemini(
        self,
        prompt: str,
        aspect_ratio: str = '1:1',
        fast: bool = False
    ) -> Dict:
        """Generiert ein Bild mit Google Gemini Imagen 3"""
        if not self.gemini_client:
            return {'success': False, 'error': 'Gemini API-Key nicht konfiguriert'}

        try:
            start_time = time.time()

            # Imagen 3 oder Imagen 3 Fast
            model_id = 'imagen-3.0-fast-generate-001' if fast else 'imagen-3.0-generate-002'

            # Gemini Imagen 3 mit google-genai SDK
            response = self.gemini_client.models.generate_images(
                model=model_id,
                prompt=prompt,
                config=genai_types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    person_generation='allow_adult',
                )
            )

            if response.generated_images:
                # Bild-Daten extrahieren
                image_data = response.generated_images[0].image._pil_image
                duration = time.time() - start_time

                return {
                    'success': True,
                    'image_data': image_data,
                    'model': 'imagen-3.0-fast' if fast else 'imagen-3.0',
                    'duration': duration
                }
            else:
                return {'success': False, 'error': 'Keine Bilder generiert'}

        except Exception as e:
            logger.error(f"Gemini Imagen error: {e}")
            return {'success': False, 'error': str(e)}

    def _size_to_aspect_ratio(self, size: str) -> str:
        """Konvertiert Größe zu Aspect Ratio für Gemini"""
        mapping = {
            '1024x1024': '1:1',
            '1792x1024': '16:9',
            '1024x1792': '9:16',
            '512x512': '1:1',
        }
        return mapping.get(size, '1:1')

    def generate_image(
        self,
        prompt: str,
        style: str = 'cinematic',
        model: str = 'dall-e-3',
        format: str = '1024x1024',
        context: str = ''
    ) -> Dict:
        """
        Generiert ein einzelnes Bild.

        Args:
            prompt: Basis-Prompt für das Bild
            style: Bildstil
            model: KI-Modell (dall-e-3, dall-e-2, gemini)
            format: Bildformat/Größe
            context: Zusätzlicher Kontext (z.B. Skript-Thema)

        Returns:
            Dict mit success, image_url/image_data, etc.
        """
        # Prompt erweitern
        enhanced_prompt = self._enhance_prompt(prompt, style, context)

        if model in ['dall-e-3', 'dall-e-2']:
            result = self._generate_with_dalle(
                prompt=enhanced_prompt,
                model=model,
                size=format
            )
        elif model in ['gemini', 'gemini-fast']:
            aspect_ratio = self._size_to_aspect_ratio(format)
            result = self._generate_with_gemini(
                prompt=enhanced_prompt,
                aspect_ratio=aspect_ratio,
                fast=(model == 'gemini-fast')
            )
        else:
            return {'success': False, 'error': f'Unbekanntes Modell: {model}'}

        if result['success']:
            result['original_prompt'] = prompt
            result['enhanced_prompt'] = enhanced_prompt
            result['style'] = style
            result['format'] = format

        return result

    def generate_prompts_from_script(
        self,
        script: str,
        interval_seconds: int,
        duration_minutes: float,
        keyword: str
    ) -> List[Dict]:
        """
        Generiert Bild-Prompts basierend auf dem Skript.

        Args:
            script: Das Videoskript
            interval_seconds: Intervall zwischen Bildern in Sekunden
            duration_minutes: Gesamtdauer des Videos in Minuten
            keyword: Hauptthema/Keyword

        Returns:
            Liste von Dicts mit position_seconds und prompt
        """
        total_seconds = duration_minutes * 60
        num_images = int(total_seconds / interval_seconds)

        # Skript in Segmente teilen
        words = script.split()
        words_per_image = max(1, len(words) // num_images) if num_images > 0 else len(words)

        prompts = []
        for i in range(num_images):
            position = i * interval_seconds
            start_word = i * words_per_image
            end_word = min(start_word + words_per_image, len(words))

            # Segment des Skripts für dieses Bild
            segment = ' '.join(words[start_word:end_word])

            # Prompt generieren basierend auf Segment
            if segment.strip():
                # Kernaussage aus Segment extrahieren (vereinfacht)
                prompt = self._extract_visual_prompt(segment, keyword)
            else:
                prompt = f"Visual representation of {keyword}"

            prompts.append({
                'position_seconds': position,
                'order': i,
                'prompt': prompt,
                'segment': segment[:200]  # Segment für Referenz
            })

        return prompts

    def _extract_visual_prompt(self, text: str, keyword: str) -> str:
        """Extrahiert einen visuellen Prompt aus einem Textsegment"""
        # Bereinige den Text
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()

        # Wichtige Wörter identifizieren (Nomen, Adjektive, Verben)
        # Vereinfachte Version - nimmt die ersten relevanten Wörter
        key_words = []
        skip_words = {'du', 'ich', 'wir', 'sie', 'er', 'es', 'das', 'die', 'der',
                      'und', 'oder', 'aber', 'wenn', 'dann', 'also', 'denn',
                      'ein', 'eine', 'einer', 'einem', 'einen', 'ist', 'sind',
                      'hat', 'haben', 'wird', 'werden', 'kann', 'können'}

        for word in words:
            if word.lower() not in skip_words and len(word) > 2:
                key_words.append(word)
                if len(key_words) >= 8:
                    break

        if key_words:
            visual_elements = ' '.join(key_words)
            return f"{keyword}: {visual_elements}"
        else:
            return f"Visual scene about {keyword}"

    def download_image_from_url(self, url: str) -> Optional[bytes]:
        """Lädt ein Bild von einer URL herunter"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    def save_image_to_model(self, image_instance, image_url: str = None, image_data=None):
        """
        Speichert ein Bild in das Model.

        Args:
            image_instance: VSkriptImage Instanz
            image_url: URL des Bildes (für DALL-E)
            image_data: PIL Image Daten (für Gemini)
        """
        try:
            if image_url:
                # Bild von URL herunterladen
                image_content = self.download_image_from_url(image_url)
                if image_content:
                    filename = f"vskript_{image_instance.project.id}_{image_instance.order}.png"
                    image_instance.image_file.save(
                        filename,
                        ContentFile(image_content),
                        save=False
                    )
                image_instance.image_url = image_url

            elif image_data:
                # PIL Image speichern
                buffer = BytesIO()
                image_data.save(buffer, format='PNG')
                buffer.seek(0)

                filename = f"vskript_{image_instance.project.id}_{image_instance.order}.png"
                image_instance.image_file.save(
                    filename,
                    ContentFile(buffer.getvalue()),
                    save=False
                )

            image_instance.save()
            return True

        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return False

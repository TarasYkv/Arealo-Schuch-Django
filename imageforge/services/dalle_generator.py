"""
OpenAI Image Generator für ImageForge

Unterstützt:
- GPT-4o Image (gpt-image-1) - Neuestes Modell, bis 4K, transparente Hintergründe
- DALL-E 3 - Kreativ & künstlerisch, versteht komplexe Prompts
- DALL-E 2 - Schneller, gut für einfache Bilder
"""

import logging
import requests
from typing import Dict, List, Optional, Any

from .base_generator import BaseImageGenerator

logger = logging.getLogger(__name__)


class DalleGenerator(BaseImageGenerator):
    """
    Bild-Generator für OpenAI DALL-E Modelle.
    """

    BASE_URL = "https://api.openai.com/v1/images/generations"

    # Verfügbare Modelle
    AVAILABLE_MODELS = {
        'gpt-image-1': 'GPT-4o Image (Beste Qualität, bis 4K)',
        'dall-e-3': 'DALL-E 3 (Kreativ & künstlerisch)',
        'dall-e-2': 'DALL-E 2 (Schnell)',
    }

    # Unterstützte Größen pro Modell
    GPT_IMAGE_SIZES = ['1024x1024', '1024x1536', '1536x1024']
    DALLE3_SIZES = ['1024x1024', '1792x1024', '1024x1792']
    DALLE2_SIZES = ['256x256', '512x512', '1024x1024']

    DEFAULT_MODEL = 'gpt-image-1'

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def get_available_models(self) -> Dict[str, str]:
        return self.AVAILABLE_MODELS.copy()

    def generate(
        self,
        prompt: str,
        reference_images: Optional[List[Any]] = None,
        width: int = 1024,
        height: int = 1024,
        model: Optional[str] = None,
        quality: str = 'standard'
    ) -> Dict[str, Any]:
        """
        Generiert ein Bild mit DALL-E.

        Hinweis: DALL-E unterstützt keine Referenzbilder direkt.
        Referenzbilder werden in den Prompt integriert (Beschreibung).

        Args:
            prompt: Vollständiger Prompt
            reference_images: Werden ignoriert (DALL-E unterstützt keine Referenzen)
            width: Bildbreite
            height: Bildhöhe
            model: Modell-ID
            quality: 'standard' oder 'hd' (nur DALL-E 3)

        Returns:
            Dict mit success, image_data/error, model_used
        """
        selected_model = model if model in self.AVAILABLE_MODELS else self.DEFAULT_MODEL

        # Warnung bei Referenzbildern
        if reference_images:
            logger.warning("DALL-E supports no reference images - they will be ignored")

        try:
            # Bestimme die passende Größe
            size = self._get_best_size(width, height, selected_model)

            # Baue Request
            payload = {
                "model": selected_model,
                "prompt": prompt,
                "n": 1,
                "size": size,
            }

            # Modell-spezifische Optionen
            if selected_model == 'gpt-image-1':
                payload["response_format"] = "b64_json"
                payload["output_format"] = "png"
                # GPT-Image-1 Qualität: low, medium, high
                if quality == 'hd':
                    payload["quality"] = "high"
                else:
                    payload["quality"] = "medium"
            elif selected_model == 'dall-e-3':
                payload["response_format"] = "b64_json"
                if quality == 'hd':
                    payload["quality"] = "hd"
            else:
                payload["response_format"] = "b64_json"

            logger.info(f"Calling DALL-E API: {selected_model}, Size: {size}")
            logger.info(f"Prompt: {prompt[:100]}...")

            response = requests.post(
                self.BASE_URL,
                json=payload,
                headers=self.headers,
                timeout=120
            )

            if response.status_code == 200:
                return self._parse_response(response.json(), selected_model)
            else:
                error_msg = f"API Fehler: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                logger.error(f"DALL-E API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'model_used': selected_model
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout bei der Bildgenerierung. Bitte erneut versuchen.',
                'model_used': selected_model
            }
        except Exception as e:
            logger.error(f"Error in DALL-E generation: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_used': selected_model
            }

    def _parse_response(self, data: dict, model: str) -> Dict[str, Any]:
        """Parst DALL-E API Response"""
        try:
            if "data" in data and len(data["data"]) > 0:
                image_data = data["data"][0].get("b64_json")
                if image_data:
                    logger.info("Image extracted from DALL-E response")

                    # DALL-E 3 gibt manchmal einen überarbeiteten Prompt zurück
                    revised_prompt = data["data"][0].get("revised_prompt")
                    if revised_prompt:
                        logger.info(f"DALL-E revised prompt: {revised_prompt[:100]}...")

                    return {
                        'success': True,
                        'image_data': image_data,
                        'model_used': model,
                        'revised_prompt': revised_prompt
                    }

            return {
                'success': False,
                'error': 'Keine Bilddaten in der DALL-E-Antwort',
                'model_used': model
            }

        except Exception as e:
            logger.error(f"Error parsing DALL-E response: {e}")
            return {
                'success': False,
                'error': f'Fehler beim Parsen: {str(e)}',
                'model_used': model
            }

    def _get_best_size(self, width: int, height: int, model: str) -> str:
        """
        Bestimmt die beste unterstützte Größe für das Modell.

        GPT-Image-1 Größen: 1024x1024, 1024x1536, 1536x1024
        DALL-E 3 Größen: 1024x1024, 1792x1024, 1024x1792
        DALL-E 2 Größen: 256x256, 512x512, 1024x1024
        """
        ratio = width / height

        if model == 'gpt-image-1':
            if ratio > 1.3:
                return '1536x1024'  # Landscape
            elif ratio < 0.8:
                return '1024x1536'  # Portrait
            else:
                return '1024x1024'  # Square
        elif model == 'dall-e-3':
            if ratio > 1.5:
                return '1792x1024'  # Landscape
            elif ratio < 0.7:
                return '1024x1792'  # Portrait
            else:
                return '1024x1024'  # Square
        else:
            # DALL-E 2 - nur quadratische Formate
            return '1024x1024'


class DalleEditGenerator(BaseImageGenerator):
    """
    DALL-E Edit/Inpainting Generator.

    Kann Teile eines Bildes basierend auf einer Maske neu generieren.
    Nützlich für Hintergrund-Ersetzung mit transparentem Produkt.
    """

    BASE_URL = "https://api.openai.com/v1/images/edits"

    AVAILABLE_MODELS = {
        'dall-e-2': 'DALL-E 2 (Edit/Inpainting)',
    }

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.headers = {
            "Authorization": f"Bearer {api_key}"
        }

    @property
    def provider_name(self) -> str:
        return "OpenAI (Edit)"

    def get_available_models(self) -> Dict[str, str]:
        return self.AVAILABLE_MODELS.copy()

    def generate(
        self,
        prompt: str,
        reference_images: Optional[List[Any]] = None,
        width: int = 1024,
        height: int = 1024,
        model: Optional[str] = None,
        quality: str = 'standard'
    ) -> Dict[str, Any]:
        """
        Generiert ein bearbeitetes Bild mit DALL-E 2 Edit API.

        Args:
            prompt: Beschreibung der gewünschten Änderung
            reference_images: [0] = Originalbild, [1] = Maske (optional)
            width: Bildbreite (muss quadratisch sein)
            height: Bildhöhe (muss quadratisch sein)
            model: Wird ignoriert (nur dall-e-2 unterstützt)
            quality: Wird ignoriert

        Returns:
            Dict mit success, image_data/error, model_used
        """
        if not reference_images or len(reference_images) < 1:
            return {
                'success': False,
                'error': 'DALL-E Edit benötigt mindestens ein Referenzbild',
                'model_used': 'dall-e-2'
            }

        try:
            import io

            # Originalbild vorbereiten
            original_image = reference_images[0]
            if hasattr(original_image, 'read'):
                image_data = original_image.read()
                original_image.seek(0)
            elif hasattr(original_image, 'path'):
                with open(original_image.path, 'rb') as f:
                    image_data = f.read()
            else:
                with open(str(original_image), 'rb') as f:
                    image_data = f.read()

            files = {
                'image': ('image.png', io.BytesIO(image_data), 'image/png'),
                'prompt': (None, prompt),
                'n': (None, '1'),
                'size': (None, '1024x1024'),
                'response_format': (None, 'b64_json')
            }

            # Maske hinzufügen falls vorhanden
            if len(reference_images) > 1:
                mask_image = reference_images[1]
                if hasattr(mask_image, 'read'):
                    mask_data = mask_image.read()
                    mask_image.seek(0)
                elif hasattr(mask_image, 'path'):
                    with open(mask_image.path, 'rb') as f:
                        mask_data = f.read()
                else:
                    with open(str(mask_image), 'rb') as f:
                        mask_data = f.read()
                files['mask'] = ('mask.png', io.BytesIO(mask_data), 'image/png')

            logger.info("Calling DALL-E Edit API")
            logger.info(f"Prompt: {prompt[:100]}...")

            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                files=files,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    image_data = data["data"][0].get("b64_json")
                    if image_data:
                        return {
                            'success': True,
                            'image_data': image_data,
                            'model_used': 'dall-e-2'
                        }
                return {
                    'success': False,
                    'error': 'Keine Bilddaten in der Antwort',
                    'model_used': 'dall-e-2'
                }
            else:
                error_msg = f"API Fehler: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                return {
                    'success': False,
                    'error': error_msg,
                    'model_used': 'dall-e-2'
                }

        except Exception as e:
            logger.error(f"Error in DALL-E Edit: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_used': 'dall-e-2'
            }

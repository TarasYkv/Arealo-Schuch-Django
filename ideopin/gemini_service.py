import logging
import base64
import requests
from io import BytesIO

logger = logging.getLogger(__name__)


class GeminiImageService:
    """Service für Google Gemini/Imagen 3 API Integration"""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle
    AVAILABLE_MODELS = {
        'imagen-3.0-generate-002': 'Imagen 3 (Beste Qualität)',
        'imagen-3.0-fast-generate-001': 'Imagen 3 Fast (Schneller)',
    }

    DEFAULT_MODEL = 'imagen-3.0-generate-002'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

    def generate_image(
        self,
        prompt: str,
        reference_image=None,
        width: int = 1000,
        height: int = 1500,
        model: str = None
    ) -> dict:
        """
        Generiert ein Bild mit Google Imagen 3

        Args:
            prompt: Beschreibung des gewünschten Bildes
            reference_image: Optional - Referenzbild für Editing
            width: Bildbreite
            height: Bildhöhe
            model: Imagen Modell

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        selected_model = model if model and model in self.AVAILABLE_MODELS else self.DEFAULT_MODEL
        logger.info(f"Using Gemini Imagen model: {selected_model}")

        try:
            # Bestimme Aspect Ratio
            aspect_ratio = self._get_aspect_ratio(width, height)

            # Wenn Referenzbild vorhanden, nutze Edit-Funktion
            if reference_image:
                return self._edit_image(prompt, reference_image, aspect_ratio, selected_model)

            # Standard-Generierung
            return self._generate_standard(prompt, aspect_ratio, selected_model)

        except Exception as e:
            logger.error(f"Error in Gemini image generation: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Bestimmt das Aspect Ratio für Imagen"""
        ratio = width / height
        if ratio > 1.2:
            return "16:9"
        elif ratio < 0.8:
            return "9:16"  # Pinterest-Format
        elif 0.9 <= ratio <= 1.1:
            return "1:1"
        else:
            return "3:4"  # Standard Pinterest

    def _generate_standard(self, prompt: str, aspect_ratio: str, model: str) -> dict:
        """Standard Bildgenerierung ohne Referenz"""
        try:
            # Imagen 3 API Endpoint
            url = f"{self.BASE_URL}/models/{model}:predict"

            payload = {
                "instances": [
                    {
                        "prompt": prompt
                    }
                ],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": aspect_ratio,
                    "personGeneration": "allow_adult",
                    "safetyFilterLevel": "block_medium_and_above"
                }
            }

            logger.info(f"Calling Imagen API: {url}")
            logger.info(f"Aspect ratio: {aspect_ratio}")

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                if "predictions" in data and len(data["predictions"]) > 0:
                    # Imagen gibt base64 direkt zurück
                    image_b64 = data["predictions"][0].get("bytesBase64Encoded")
                    if image_b64:
                        return {
                            'success': True,
                            'image_data': image_b64
                        }

                return {
                    'success': False,
                    'error': 'Keine Bilddaten in der Antwort'
                }
            else:
                error_msg = f"API Fehler: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                logger.error(f"Gemini API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout bei der Bildgenerierung. Bitte erneut versuchen.'
            }
        except Exception as e:
            logger.error(f"Error in Gemini standard generation: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _edit_image(self, prompt: str, reference_image, aspect_ratio: str, model: str) -> dict:
        """
        Generiert ein Bild mit Imagen 3.

        Hinweis: Die Imagen 3 API über generativelanguage unterstützt kein direktes
        Image Editing. Daher nutzen wir die Standard-Generierung.
        Das Referenzbild wird ignoriert - der Prompt sollte das gewünschte Ergebnis beschreiben.
        """
        logger.info("Reference image provided, but Imagen 3 API does not support image editing.")
        logger.info("Using standard generation instead. Consider describing the product in the prompt.")

        # Verwende Standard-Generierung
        return self._generate_standard(prompt, aspect_ratio, model)

    @staticmethod
    def build_prompt_with_text(
        background_description: str,
        overlay_text: str,
        text_position: str = 'center',
        text_style: str = 'modern',
        keywords: str = '',
        has_product_image: bool = False
    ) -> str:
        """
        Baut einen optimierten Prompt für Imagen 3 MIT integriertem Text.

        Imagen 3 ist besonders gut bei Text-Rendering.
        """
        position_map = {
            'top': 'at the top',
            'center': 'in the center',
            'bottom': 'at the bottom'
        }
        position_text = position_map.get(text_position, 'prominently displayed')

        style_descriptions = {
            'modern': 'modern, bold sans-serif typography',
            'elegant': 'elegant serif typography',
            'playful': 'playful, hand-written style',
            'bold': 'bold, impactful typography',
            'minimal': 'minimalist typography',
            'vintage': 'vintage retro typography',
        }
        style_desc = style_descriptions.get(text_style, style_descriptions['modern'])

        prompt_parts = []

        # Produktbild-Integration
        if has_product_image:
            prompt_parts.append(
                "Create a Pinterest pin featuring the product from the reference image prominently"
            )
            if background_description:
                prompt_parts.append(f"Background: {background_description.strip()}")
        else:
            if background_description:
                prompt_parts.append(background_description.strip())

        # Text-Integration - Imagen 3 ist sehr gut mit Text
        if overlay_text:
            prompt_parts.append(
                f'Display the text "{overlay_text}" {position_text} using {style_desc}. '
                f'The text must be perfectly readable, large, and have high contrast. '
                f'No spelling errors in the text.'
            )

        # Qualitäts-Keywords
        quality_keywords = [
            "Pinterest pin design",
            "professional quality",
            "high resolution",
            "visually striking",
            "perfect typography"
        ]
        prompt_parts.extend(quality_keywords)

        final_prompt = ". ".join(prompt_parts)
        logger.info(f"Built Gemini prompt with text: {final_prompt[:150]}...")
        return final_prompt

    @staticmethod
    def build_prompt_without_text(
        background_description: str,
        keywords: str = '',
        has_product_image: bool = False
    ) -> str:
        """Baut einen Prompt für Bildgenerierung OHNE Text."""
        prompt_parts = []

        if has_product_image:
            prompt_parts.append(
                "Create a Pinterest pin featuring the product from the reference image"
            )
            if background_description:
                prompt_parts.append(f"Background: {background_description.strip()}")
            prompt_parts.append("Leave clean space for text overlay")
        else:
            if background_description:
                prompt_parts.append(background_description.strip())

        quality_keywords = [
            "Pinterest pin background",
            "professional quality",
            "clean design",
            "space for text"
        ]
        prompt_parts.extend(quality_keywords)

        final_prompt = ". ".join(prompt_parts)
        logger.info(f"Built Gemini prompt without text: {final_prompt[:150]}...")
        return final_prompt

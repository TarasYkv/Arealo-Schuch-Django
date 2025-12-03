import logging
import base64
import requests
from io import BytesIO

logger = logging.getLogger(__name__)


class GeminiImageService:
    """
    Service für Google Gemini Image Generation (Nano Banana / Nano Banana Pro)

    Diese Modelle können:
    - Bilder mit Text-Overlay generieren
    - Produkte aus Referenzbildern extrahieren und in neue Bilder integrieren
    - Text korrekt und ohne Fehler rendern
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle - Nano Banana Familie
    AVAILABLE_MODELS = {
        'gemini-2.0-flash-exp': 'Gemini 2.0 Flash (Nano Banana)',
        'gemini-2.0-flash-preview-image-generation': 'Gemini 2.0 Flash Preview',
    }

    DEFAULT_MODEL = 'gemini-2.0-flash-exp'

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
        Generiert ein Bild mit Gemini (Nano Banana)

        Args:
            prompt: Beschreibung des gewünschten Bildes
            reference_image: Optional - Produktbild das integriert werden soll
            width: Bildbreite
            height: Bildhöhe
            model: Gemini Modell

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        selected_model = model if model and model in self.AVAILABLE_MODELS else self.DEFAULT_MODEL
        logger.info(f"Using Gemini model: {selected_model}")

        try:
            # Bestimme Aspect Ratio
            aspect_ratio = self._get_aspect_ratio(width, height)

            # API Endpoint für generateContent
            url = f"{self.BASE_URL}/models/{selected_model}:generateContent"

            # Baue die Request Parts
            parts = [{"text": prompt}]

            # Wenn Referenzbild vorhanden, füge es hinzu
            if reference_image:
                image_b64 = self._read_image_as_base64(reference_image)
                if image_b64:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_b64
                        }
                    })
                    logger.info("Reference image added to request")

            payload = {
                "contents": [{
                    "parts": parts
                }],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                }
            }

            logger.info(f"Calling Gemini API: {url}")
            logger.info(f"Prompt: {prompt[:100]}...")

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=180  # Längerer Timeout für Bildgenerierung
            )

            if response.status_code == 200:
                return self._parse_response(response.json())
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
            logger.error(f"Error in Gemini image generation: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _read_image_as_base64(self, reference_image) -> str:
        """Liest ein Bild und gibt es als Base64 zurück"""
        try:
            if hasattr(reference_image, 'read'):
                image_data = reference_image.read()
                reference_image.seek(0)
            elif hasattr(reference_image, 'path'):
                with open(reference_image.path, 'rb') as f:
                    image_data = f.read()
            else:
                with open(reference_image, 'rb') as f:
                    image_data = f.read()

            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading reference image: {e}")
            return None

    def _parse_response(self, data: dict) -> dict:
        """Parst die Gemini API Response und extrahiert das Bild"""
        try:
            if "candidates" not in data or len(data["candidates"]) == 0:
                return {
                    'success': False,
                    'error': 'Keine Antwort vom Modell erhalten'
                }

            candidate = data["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Suche nach dem Bild in den Parts
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"].get("data")
                    if image_data:
                        logger.info("Image successfully extracted from response")
                        return {
                            'success': True,
                            'image_data': image_data
                        }
                # Alternativ: inline_data (unterschiedliche API-Versionen)
                if "inline_data" in part:
                    image_data = part["inline_data"].get("data")
                    if image_data:
                        logger.info("Image successfully extracted from response")
                        return {
                            'success': True,
                            'image_data': image_data
                        }

            # Kein Bild gefunden - prüfe ob Text-Antwort
            for part in parts:
                if "text" in part:
                    text = part["text"]
                    logger.warning(f"Got text response instead of image: {text[:200]}")
                    return {
                        'success': False,
                        'error': f'Modell hat Text statt Bild generiert: {text[:100]}...'
                    }

            return {
                'success': False,
                'error': 'Keine Bilddaten in der Antwort gefunden'
            }

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return {
                'success': False,
                'error': f'Fehler beim Parsen der Antwort: {str(e)}'
            }

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Bestimmt das Aspect Ratio"""
        ratio = width / height
        if ratio > 1.5:
            return "16:9"
        elif ratio < 0.7:
            return "9:16"  # Pinterest-Format
        elif 0.9 <= ratio <= 1.1:
            return "1:1"
        else:
            return "3:4"  # Standard Pinterest

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
        Baut einen optimierten Prompt für Gemini MIT integriertem Text.

        Gemini (Nano Banana) kann:
        - Text perfekt und ohne Fehler rendern
        - Produkte aus Referenzbildern extrahieren und integrieren
        """
        position_map = {
            'top': 'at the top of the image',
            'center': 'in the center of the image',
            'bottom': 'at the bottom of the image'
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

        # Produktbild-Integration - Gemini kann das Produkt aus dem Referenzbild extrahieren
        if has_product_image:
            prompt_parts.append(
                "Create a Pinterest pin design. "
                "Extract the product from the provided reference image and place it prominently in the new design. "
                "Keep the product exactly as it appears - do not modify, distort, or reimagine the product itself."
            )
            if background_description:
                prompt_parts.append(f"Create this background around the product: {background_description.strip()}")
        else:
            if background_description:
                prompt_parts.append(f"Create a Pinterest pin with this scene: {background_description.strip()}")

        # Text-Integration - Gemini ist sehr gut mit Text
        if overlay_text:
            prompt_parts.append(
                f'Add the text "{overlay_text}" {position_text} using {style_desc}. '
                f'The text must be perfectly spelled, large, bold and highly readable with strong contrast. '
                f'Make sure every letter is correct and clearly visible.'
            )

        # Format und Qualität
        prompt_parts.append(
            "Create a vertical Pinterest pin format (2:3 ratio). "
            "Professional quality, high resolution, visually striking design."
        )

        final_prompt = " ".join(prompt_parts)
        logger.info(f"Built Gemini prompt with text: {final_prompt[:200]}...")
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
                "Create a Pinterest pin design. "
                "Extract the product from the provided reference image and place it prominently. "
                "Keep the product exactly as it appears in the original."
            )
            if background_description:
                prompt_parts.append(f"Background: {background_description.strip()}")
            prompt_parts.append("Leave clean space for text overlay to be added later.")
        else:
            if background_description:
                prompt_parts.append(f"Create: {background_description.strip()}")

        prompt_parts.append(
            "Vertical Pinterest pin format (2:3 ratio). "
            "Professional quality, clean design with space for text."
        )

        final_prompt = " ".join(prompt_parts)
        logger.info(f"Built Gemini prompt without text: {final_prompt[:200]}...")
        return final_prompt

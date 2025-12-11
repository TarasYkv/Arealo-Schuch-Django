"""
Gemini/Imagen Image Generator für ImageForge

Unterstützt:
- Gemini 2.5 Flash Image (Nano Banana) - Schnelle Bildgenerierung
- Gemini 3 Pro Image (Nano Banana Pro) - Beste Qualität
- Imagen 4 Familie - Spezialisierte Bildgenerierung
"""

import logging
import requests
from typing import Dict, List, Optional, Any

from .base_generator import BaseImageGenerator

logger = logging.getLogger(__name__)


class GeminiGenerator(BaseImageGenerator):
    """
    Bild-Generator für Google Gemini und Imagen Modelle.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle
    AVAILABLE_MODELS = {
        # Gemini (Nano Banana)
        'gemini-2.5-flash-image': 'Nano Banana (Schnell)',
        'gemini-3-pro-image-preview': 'Nano Banana Pro (Beste Qualität)',
        # Imagen 4
        'imagen-4.0-ultra-generate-001': 'Imagen 4 Ultra',
        'imagen-4.0-generate-001': 'Imagen 4 Standard',
        'imagen-4.0-fast-generate-001': 'Imagen 4 Fast',
    }

    # Modelle die predict API nutzen (Imagen)
    PREDICT_MODELS = [
        'imagen-4.0-ultra-generate-001',
        'imagen-4.0-generate-001',
        'imagen-4.0-fast-generate-001',
    ]

    DEFAULT_MODEL = 'gemini-2.5-flash-image'

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

    @property
    def provider_name(self) -> str:
        return "Google"

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
        Generiert ein Bild mit Gemini oder Imagen.

        Args:
            prompt: Vollständiger Prompt
            reference_images: Liste von Referenzbildern (Produkt/Charakter)
            width: Bildbreite
            height: Bildhöhe
            model: Modell-ID
            quality: Qualitätsstufe (wird bei Gemini ignoriert)

        Returns:
            Dict mit success, image_data/error, model_used
        """
        selected_model = model if model in self.AVAILABLE_MODELS else self.DEFAULT_MODEL

        try:
            # Aspect Ratio bestimmen
            aspect_ratio = self._get_aspect_ratio(width, height)

            # Wähle API-Endpunkt basierend auf Modell
            if selected_model in self.PREDICT_MODELS:
                result = self._generate_with_imagen(prompt, aspect_ratio, selected_model)
            else:
                result = self._generate_with_gemini(prompt, reference_images, aspect_ratio, selected_model)

            result['model_used'] = selected_model
            return result

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout bei der Bildgenerierung. Bitte erneut versuchen.',
                'model_used': selected_model
            }
        except Exception as e:
            logger.error(f"Error in Gemini generation: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_used': selected_model
            }

    def _generate_with_gemini(
        self,
        prompt: str,
        reference_images: Optional[List[Any]],
        aspect_ratio: str,
        model: str
    ) -> Dict[str, Any]:
        """Generiert Bild mit Gemini (generateContent API)"""
        url = f"{self.BASE_URL}/models/{model}:generateContent"

        # Baue Request Parts
        parts = [{"text": prompt}]

        # Referenzbilder hinzufügen
        if reference_images:
            for ref_image in reference_images:
                image_b64 = self._read_image_as_base64(ref_image)
                if image_b64:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_b64
                        }
                    })
                    logger.info("Reference image added to Gemini request")

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio
                }
            }
        }

        logger.info(f"Calling Gemini API: {model}, Aspect Ratio: {aspect_ratio}")
        logger.info(f"Prompt: {prompt[:100]}...")

        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=180
        )

        if response.status_code == 200:
            return self._parse_gemini_response(response.json())
        else:
            error_msg = f"API Fehler: {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = error_data['error'].get('message', error_msg)
            except:
                pass
            logger.error(f"Gemini API error: {error_msg}")
            return {'success': False, 'error': error_msg}

    def _generate_with_imagen(
        self,
        prompt: str,
        aspect_ratio: str,
        model: str
    ) -> Dict[str, Any]:
        """Generiert Bild mit Imagen (predict API)"""
        url = f"{self.BASE_URL}/models/{model}:predict"

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "personGeneration": "allow_adult",
                "safetyFilterLevel": "block_medium_and_above"
            }
        }

        logger.info(f"Calling Imagen API: {model}")
        logger.info(f"Prompt: {prompt[:100]}...")

        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=180
        )

        if response.status_code == 200:
            return self._parse_imagen_response(response.json())
        else:
            error_msg = f"API Fehler: {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = error_data['error'].get('message', error_msg)
            except:
                pass
            logger.error(f"Imagen API error: {error_msg}")
            return {'success': False, 'error': error_msg}

    def _parse_gemini_response(self, data: dict) -> Dict[str, Any]:
        """Parst Gemini API Response"""
        try:
            if "candidates" not in data or len(data["candidates"]) == 0:
                return {'success': False, 'error': 'Keine Antwort vom Modell erhalten'}

            candidate = data["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Suche nach Bild in Parts
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"].get("data")
                    if image_data:
                        logger.info("Image extracted from Gemini response")
                        return {'success': True, 'image_data': image_data}
                if "inline_data" in part:
                    image_data = part["inline_data"].get("data")
                    if image_data:
                        logger.info("Image extracted from Gemini response")
                        return {'success': True, 'image_data': image_data}

            # Kein Bild - prüfe auf Text
            for part in parts:
                if "text" in part:
                    text = part["text"]
                    logger.warning(f"Got text instead of image: {text[:200]}")
                    return {'success': False, 'error': f'Modell hat Text statt Bild generiert: {text[:100]}...'}

            return {'success': False, 'error': 'Keine Bilddaten in der Antwort'}

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return {'success': False, 'error': f'Fehler beim Parsen: {str(e)}'}

    def _parse_imagen_response(self, data: dict) -> Dict[str, Any]:
        """Parst Imagen API Response"""
        try:
            if "predictions" in data and len(data["predictions"]) > 0:
                image_b64 = data["predictions"][0].get("bytesBase64Encoded")
                if image_b64:
                    logger.info("Image extracted from Imagen response")
                    return {'success': True, 'image_data': image_b64}

            return {'success': False, 'error': 'Keine Bilddaten in der Imagen-Antwort'}

        except Exception as e:
            logger.error(f"Error parsing Imagen response: {e}")
            return {'success': False, 'error': f'Fehler beim Parsen: {str(e)}'}

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Bestimmt Aspect Ratio aus Dimensionen"""
        ratio = width / height

        if width == height:
            return "1:1"
        elif ratio > 1.7:
            return "16:9"
        elif ratio < 0.6:
            return "9:16"
        elif 0.6 <= ratio < 0.8:
            return "3:4"
        elif 1.2 < ratio <= 1.4:
            return "4:3"
        else:
            return "1:1"

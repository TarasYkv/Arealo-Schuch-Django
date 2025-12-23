import logging
import base64
import requests

logger = logging.getLogger(__name__)


def spell_out_text(text: str, min_word_length: int = 6) -> str:
    """
    Buchstabiert lange Wörter im Text für bessere KI-Textgenauigkeit.

    Beispiel: "Geburtstagsgeschenke" -> "G-e-b-u-r-t-s-t-a-g-s-g-e-s-c-h-e-n-k-e"

    Args:
        text: Der zu buchstabierende Text
        min_word_length: Minimale Wortlänge für Buchstabierung (Default: 6)

    Returns:
        Text mit buchstabierten langen Wörtern
    """
    words = text.split()
    spelled_words = []

    for word in words:
        # Entferne Satzzeichen für die Längenprüfung
        clean_word = ''.join(c for c in word if c.isalnum())

        if len(clean_word) >= min_word_length:
            # Buchstabiere das Wort, behalte Satzzeichen am Ende
            trailing_punct = ''
            if word and not word[-1].isalnum():
                trailing_punct = word[-1]
                word = word[:-1]

            spelled = '-'.join(list(word))
            spelled_words.append(f'"{word}" (spelled: {spelled}){trailing_punct}')
        else:
            spelled_words.append(word)

    return ' '.join(spelled_words)


class GeminiImageService:
    """
    Service für Google Gemini/Imagen Image Generation

    Unterstützt:
    - Gemini 2.5 Flash (Nano Banana) - Native Bildgenerierung mit Chat
    - Gemini 3 Pro Image - Neueste Generation
    - Imagen 4 Familie - Spezialisierte Bildgenerierung
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle für Bildgenerierung
    AVAILABLE_MODELS = {
        # Gemini Image Generation Modelle (Nano Banana)
        'gemini-3-pro-image-preview': 'Gemini 3 Pro Image (Nano Banana Pro - Beste Qualität)',
        'gemini-2.5-flash-image': 'Gemini 2.5 Flash Image (Nano Banana - Schnell)',
        # Imagen 4 Familie (spezialisierte Bildgenerierung)
        'imagen-4.0-ultra-generate-001': 'Imagen 4 Ultra',
        'imagen-4.0-generate-001': 'Imagen 4 Standard',
        'imagen-4.0-fast-generate-001': 'Imagen 4 Fast',
    }

    # Modelle die predict nutzen (Imagen)
    PREDICT_MODELS = [
        'imagen-4.0-generate-001',
        'imagen-4.0-fast-generate-001',
        'imagen-4.0-ultra-generate-001',
    ]

    DEFAULT_MODEL = 'gemini-2.5-flash-image'

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
        Generiert ein Bild mit Gemini/Imagen

        Args:
            prompt: Beschreibung des gewünschten Bildes
            reference_image: Optional - Produktbild das integriert werden soll
            width: Bildbreite
            height: Bildhöhe
            model: Modell-ID

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        logger.info(f"[Gemini] Received model parameter: '{model}'")
        logger.info(f"[Gemini] Available models: {list(self.AVAILABLE_MODELS.keys())}")
        if model and model in self.AVAILABLE_MODELS:
            selected_model = model
            logger.info(f"[Gemini] Using requested model: {selected_model}")
        else:
            selected_model = self.DEFAULT_MODEL
            logger.warning(f"[Gemini] Model '{model}' not found or None, using default: {selected_model}")

        try:
            # Bestimme Aspect Ratio
            aspect_ratio = self._get_aspect_ratio(width, height)

            # Wähle API-Endpunkt basierend auf Modell-Typ
            if selected_model in self.PREDICT_MODELS:
                # Imagen 4 nutzt predict Endpoint
                return self._generate_with_imagen(prompt, aspect_ratio, selected_model)
            else:
                # Gemini nutzt generateContent Endpoint
                return self._generate_with_gemini(prompt, reference_image, aspect_ratio, selected_model)

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout bei der Bildgenerierung. Bitte erneut versuchen.'
            }
        except Exception as e:
            logger.error(f"Error in image generation: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_with_gemini(self, prompt: str, reference_image, aspect_ratio: str, model: str) -> dict:
        """Generiert Bild mit Gemini (generateContent API)"""
        url = f"{self.BASE_URL}/models/{model}:generateContent"

        # Baue die Request Parts
        parts = [{"text": prompt}]

        # Wenn Referenzbild vorhanden, füge es hinzu
        logger.info(f"[Gemini] reference_image parameter: {reference_image}, type: {type(reference_image)}")
        if reference_image:
            logger.info(f"[Gemini] Attempting to read reference image...")
            image_b64 = self._read_image_as_base64(reference_image)
            if image_b64:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_b64
                    }
                })
                logger.info(f"Reference image added to Gemini request (size: {len(image_b64)} chars)")
            else:
                logger.warning("[Gemini] Failed to read reference image - image_b64 is empty")

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

        logger.info(f"Calling Gemini API: {url}")
        logger.info(f"Prompt: {prompt[:100]}...")
        logger.info(f"Aspect Ratio: {aspect_ratio}")

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
            return {
                'success': False,
                'error': error_msg
            }

    def _generate_with_imagen(self, prompt: str, aspect_ratio: str, model: str) -> dict:
        """Generiert Bild mit Imagen 4 (predict API)"""
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
            return {
                'success': False,
                'error': error_msg
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

    def _parse_gemini_response(self, data: dict) -> dict:
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
                        logger.info("Image successfully extracted from Gemini response")
                        return {
                            'success': True,
                            'image_data': image_data
                        }
                # Alternativ: inline_data (unterschiedliche API-Versionen)
                if "inline_data" in part:
                    image_data = part["inline_data"].get("data")
                    if image_data:
                        logger.info("Image successfully extracted from Gemini response")
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

    def _parse_imagen_response(self, data: dict) -> dict:
        """Parst die Imagen API Response und extrahiert das Bild"""
        try:
            if "predictions" in data and len(data["predictions"]) > 0:
                image_b64 = data["predictions"][0].get("bytesBase64Encoded")
                if image_b64:
                    logger.info("Image successfully extracted from Imagen response")
                    return {
                        'success': True,
                        'image_data': image_b64
                    }

            return {
                'success': False,
                'error': 'Keine Bilddaten in der Imagen-Antwort'
            }

        except Exception as e:
            logger.error(f"Error parsing Imagen response: {e}")
            return {
                'success': False,
                'error': f'Fehler beim Parsen der Imagen-Antwort: {str(e)}'
            }

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Bestimmt das Aspect Ratio basierend auf Bildmaßen"""
        ratio = width / height

        # Exakte Formate zuerst prüfen
        if width == 1000 and height == 1500:
            return "2:3"  # Pinterest Standard
        elif width == 1080 and height == 1920:
            return "9:16"  # Story Format
        elif width == 600 and height == 900:
            return "2:3"  # Kompakt Pinterest
        elif width == height:
            return "1:1"  # Quadratisch

        # Fallback basierend auf Verhältnis
        if ratio > 1.5:
            return "16:9"
        elif ratio < 0.6:
            return "9:16"
        elif 0.6 <= ratio < 0.75:
            return "2:3"  # Pinterest-Format (hochkant)
        elif 0.9 <= ratio <= 1.1:
            return "1:1"
        else:
            return "3:4"

    @staticmethod
    def build_prompt_with_text(
        background_description: str,
        overlay_text: str,
        text_position: str = 'center',
        text_style: str = 'modern',
        keywords: str = '',
        has_product_image: bool = False,
        text_color: str = '#FFFFFF',
        text_effect: str = 'shadow',
        text_secondary_color: str = '#000000',
        style_preset: str = 'modern_bold',
        text_background_enabled: bool = False,
        text_background_creative: bool = False
    ) -> str:
        """
        Baut einen optimierten Prompt für Gemini MIT integriertem Text.

        Die KI wählt selbst den besten Text-Style passend zum Bild.

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

        # Text-Integration - KI wählt selbst den besten Style
        if overlay_text:
            # Buchstabiere lange Wörter für bessere Genauigkeit
            spelled_text = spell_out_text(overlay_text)

            text_styling = f'CRITICAL TEXT REQUIREMENT:\n'
            text_styling += f'Display text: "{overlay_text}" {position_text}\n\n'

            # Wenn Text buchstabiert wurde, füge die Buchstabierung hinzu
            if spelled_text != overlay_text:
                text_styling += f'Spelling: {spelled_text}\n\n'

            # Text-Hintergrund Anweisungen
            if text_background_enabled:
                text_styling += f'TEXT BACKGROUND DESIGN:\n'
                text_styling += '- Place the text on a solid or semi-transparent background shape\n'
                text_styling += '- The background shape should fit the text perfectly with appropriate padding\n'
                text_styling += '- Choose a background color that complements the image but creates contrast for the text\n'
                if text_background_creative:
                    text_styling += '- Use CREATIVE shapes for the background: banner, ribbon, splash, brush stroke, torn paper, badge, stamp, or artistic geometric forms\n'
                    text_styling += '- The shape should add visual interest and match the mood of the image\n'
                else:
                    text_styling += '- Use a clean, simple shape: rectangle, rounded rectangle, or pill shape\n'
                text_styling += '\n'

            text_styling += f'TYPOGRAPHY DESIGN:\n'
            text_styling += '- Choose typography that MATCHES the mood and theme of the background image\n'
            text_styling += '- Use colors that create STRONG CONTRAST for readability but harmonize with the image palette\n'
            text_styling += '- Add subtle effects (shadow, glow, outline) that complement the image style\n'
            text_styling += '- The text should feel like a natural, professional part of the design\n\n'

            text_styling += f'TEXT RULES:\n'
            text_styling += '- Spelling must be 100% accurate\n'
            text_styling += '- Text must be LARGE and bold\n'
            text_styling += '- High contrast for readability, but colors that fit the image'
            prompt_parts.append(text_styling)

        # Format und Qualität - WICHTIG: Vertikales Pinterest-Format explizit betonen
        prompt_parts.append(
            "IMPORTANT: Create a VERTICAL Pinterest pin image with 2:3 aspect ratio (portrait orientation, taller than wide). "
            "Professional quality, high resolution, visually striking design optimized for Pinterest."
        )

        final_prompt = " ".join(prompt_parts)
        logger.info(f"Built Gemini prompt with text: {final_prompt[:300]}...")
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

    @staticmethod
    def build_prompt_for_text_overlay(
        overlay_text: str,
        text_position: str = 'center',
        text_color: str = '#FFFFFF',
        text_background_enabled: bool = False,
        text_background_creative: bool = False
    ) -> str:
        """
        Baut einen Prompt für das Hinzufügen von Text zu einem BESTEHENDEN Bild.

        Das Bild wird als Referenz mitgesendet und die KI soll NUR den Text hinzufügen,
        ohne den Hintergrund zu verändern.
        """
        position_map = {
            'top': 'at the top of the image',
            'center': 'in the center of the image',
            'bottom': 'at the bottom of the image'
        }
        position_text = position_map.get(text_position, 'prominently displayed')

        # Buchstabiere lange Wörter für bessere Genauigkeit
        spelled_text = spell_out_text(overlay_text)

        prompt_parts = []

        # Hauptanweisung: Bild behalten, nur Text hinzufügen
        prompt_parts.append(
            "IMPORTANT: Take the provided image and ADD TEXT OVERLAY to it. "
            "DO NOT change, modify, or regenerate the background image. "
            "Keep the original image EXACTLY as it is - only add the text on top."
        )

        # Text-Anforderungen
        text_section = f'\nTEXT TO ADD:\n'
        text_section += f'Display text: "{overlay_text}" {position_text}\n'

        if spelled_text != overlay_text:
            text_section += f'Spelling: {spelled_text}\n'

        prompt_parts.append(text_section)

        # Text-Hintergrund Anweisungen
        if text_background_enabled:
            bg_section = '\nTEXT BACKGROUND:\n'
            bg_section += '- Place the text on a solid or semi-transparent background shape\n'
            bg_section += '- The background shape should fit the text with appropriate padding\n'
            bg_section += '- Choose a color that creates contrast for readability\n'
            if text_background_creative:
                bg_section += '- Use CREATIVE shapes: banner, ribbon, splash, brush stroke, badge, or artistic forms\n'
            else:
                bg_section += '- Use clean shapes: rectangle, rounded rectangle, or pill shape\n'
            prompt_parts.append(bg_section)

        # Typografie-Anweisungen
        typography_section = '\nTYPOGRAPHY DESIGN:\n'
        typography_section += '- Choose typography that MATCHES the mood of the image\n'
        typography_section += '- Use colors that create STRONG CONTRAST for readability\n'
        typography_section += '- Add subtle effects (shadow, glow) for depth\n'
        typography_section += '- Text must be LARGE, bold, and professional\n'
        typography_section += '- Spelling must be 100% accurate\n'
        prompt_parts.append(typography_section)

        # Finale Anweisung
        prompt_parts.append(
            "\nOUTPUT: Return the SAME image with the text overlay added. "
            "Maintain the original image quality and aspect ratio."
        )

        final_prompt = " ".join(prompt_parts)
        logger.info(f"Built text overlay prompt: {final_prompt[:300]}...")
        return final_prompt

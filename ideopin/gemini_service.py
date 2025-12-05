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
        if reference_image:
            image_b64 = self._read_image_as_base64(reference_image)
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
        style_preset: str = 'modern_bold'
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

        # Style-Preset zu Beschreibung
        style_preset_descriptions = {
            # Modern & Clean
            'modern_bold': 'modern, bold sans-serif typography with strong visual impact',
            'minimal_clean': 'minimalist, clean typography with lots of whitespace',
            'tech_futuristic': 'futuristic tech-style typography with sleek, digital aesthetic',
            'geometric': 'geometric modern typography with clean lines and shapes',
            # Elegant & Classic
            'elegant_serif': 'elegant serif typography with classic, refined styling',
            'luxury_gold': 'luxurious gold-accented typography with premium feel',
            'wedding_romantic': 'romantic, soft typography with elegant script accents',
            'art_deco': 'Art Déco inspired typography with geometric elegance',
            # Colorful & Fun
            'playful_color': 'playful, colorful typography with fun, energetic feel',
            'neon_glow': 'vibrant neon glowing typography with electric colors',
            'pastel_soft': 'soft pastel-colored typography with gentle, dreamy feel',
            'gradient_vibrant': 'vibrant gradient typography with dynamic color transitions',
            'rainbow': 'colorful rainbow typography with playful multi-color effect',
            # Dark & Moody
            'dark_contrast': 'high-contrast dark theme with bold white or bright text',
            'midnight_blue': 'deep midnight blue theme with elegant light text',
            'noir_dramatic': 'dramatic film noir style with high contrast black and white',
            # Light & Fresh
            'bright_fresh': 'bright, fresh typography with light colors and clean lines',
            'summer_beach': 'sunny beach-inspired typography with warm, tropical colors',
            'spring_floral': 'delicate spring-inspired typography with floral accents',
            # Retro & Vintage
            'vintage_retro': 'vintage retro typography with nostalgic styling',
            'retro_70s': '1970s retro typography with groovy, warm earth tones',
            'polaroid': 'polaroid-inspired typography with vintage photo aesthetic',
            # Business & Professional
            'professional': 'professional business typography, clean and corporate',
            'corporate_blue': 'corporate blue-toned typography with trustworthy feel',
            'startup': 'modern startup typography with innovative, tech-forward style',
            # Special Themes
            'food_warm': 'warm, appetizing typography perfect for food content',
            'nature_organic': 'organic, natural typography with earthy, green tones',
            'fitness_energy': 'energetic, dynamic typography with bold, motivating style',
            'kids_playful': 'playful, child-friendly typography with fun colors',
            'christmas': 'festive Christmas typography with red, green, and gold',
            'halloween': 'spooky Halloween typography with orange, purple, and black',
        }
        style_desc = style_preset_descriptions.get(style_preset, style_preset_descriptions['modern_bold'])

        # Text-Effekt zu Beschreibung
        effect_descriptions = {
            'none': '',
            # Schatten-Varianten
            'shadow': 'with a subtle drop shadow for depth',
            'shadow_soft': 'with a soft, diffused shadow for gentle depth',
            'shadow_hard': 'with a hard, defined drop shadow',
            'shadow_long': 'with a long dramatic shadow extending from the text',
            'shadow_3d': 'with a 3D layered shadow effect creating depth',
            # Outline/Kontur
            'outline': 'with a contrasting outline/stroke around the letters',
            'outline_thin': 'with a thin, delicate outline around the letters',
            'outline_thick': 'with a thick, bold outline around the letters',
            'outline_double': 'with a double-line outline effect',
            # Leuchteffekte
            'glow': 'with a soft glowing effect',
            'glow_neon': 'with a bright neon glow effect like a neon sign',
            'glow_soft': 'with a subtle, soft ambient glow',
            # Hintergrund-Elemente
            'highlight': 'with a text highlighter effect behind the text',
            'underline': 'with a decorative underline accent',
            'box': 'inside a rectangular box background',
            'rounded_box': 'inside a rounded rectangle box background',
            'pill': 'inside a pill-shaped background',
            # Spezielle Effekte
            'frame': 'inside a decorative frame or border',
            'banner': 'on a ribbon or banner background',
            'badge': 'inside a badge or stamp design',
            'stamp': 'styled as a vintage rubber stamp',
            'torn_paper': 'on a torn paper background effect',
            'gradient_text': 'with gradient colors flowing through the text',
        }
        effect_desc = effect_descriptions.get(text_effect, '')

        # Farbe zu Beschreibung
        def hex_to_color_name(hex_color):
            color_map = {
                '#FFFFFF': 'white', '#000000': 'black', '#FF0000': 'red',
                '#00FF00': 'green', '#0000FF': 'blue', '#FFFF00': 'yellow',
                '#FF6600': 'orange', '#800080': 'purple', '#FFC0CB': 'pink',
            }
            return color_map.get(hex_color.upper(), hex_color)

        text_color_name = hex_to_color_name(text_color)
        secondary_color_name = hex_to_color_name(text_secondary_color)

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

        # Text-Integration mit detailliertem Styling und Rechtschreibhilfe
        if overlay_text:
            # Buchstabiere lange Wörter für bessere Genauigkeit
            spelled_text = spell_out_text(overlay_text)

            text_styling = f'CRITICAL TEXT REQUIREMENT: Render the following text EXACTLY as specified.\n'
            text_styling += f'Text to display: "{overlay_text}"\n'

            # Wenn Text buchstabiert wurde, füge die Buchstabierung hinzu
            if spelled_text != overlay_text:
                text_styling += f'Letter-by-letter spelling: {spelled_text}\n'

            text_styling += f'\nTEXT STYLING (MUST FOLLOW EXACTLY):\n'
            text_styling += f'- Position: {position_text}\n'
            text_styling += f'- Typography/Font style: {style_desc}\n'
            text_styling += f'- Text color: {text_color_name}\n'
            if effect_desc:
                text_styling += f'- Text effect: {effect_desc}'
                # Prüfe auf alle Schatten- und Outline-Varianten
                if text_effect.startswith('shadow') or text_effect.startswith('outline'):
                    text_styling += f' using {secondary_color_name} color'
                text_styling += '\n'

            text_styling += f'\nSPELLING RULES:\n'
            text_styling += '- Every single letter must be EXACTLY correct - no substitutions, no missing letters\n'
            text_styling += '- Double-check each word before rendering\n'
            text_styling += '- The text must be LARGE, bold, and highly readable\n'
            text_styling += '- Ensure strong contrast against the background\n'
            text_styling += '- Apply the typography style and effects specified above\n'
            text_styling += '- If unsure about a letter, refer to the letter-by-letter spelling above'
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

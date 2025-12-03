import logging
import requests
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class IdeogramService:
    """Service für Ideogram.ai API Integration"""

    BASE_URL = "https://api.ideogram.ai"

    # Aspect ratio mapping for Pinterest formats
    ASPECT_RATIOS = {
        (1000, 1500): "ASPECT_2_3",      # Pinterest Standard 2:3
        (1000, 1000): "ASPECT_1_1",      # Square
        (1080, 1920): "ASPECT_9_16",     # Story format
        (600, 900): "ASPECT_2_3",        # Compact (same ratio as standard)
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }

    # Verfügbare Modelle
    AVAILABLE_MODELS = {
        'V_2A_TURBO': 'Ideogram 2a Turbo (Beste Text-Integration)',
        'V_2A': 'Ideogram 2a (Höchste Qualität)',
        'V_2': 'Ideogram 2.0',
        'V_2_TURBO': 'Ideogram 2.0 Turbo (Schnell)',
        'V_1': 'Ideogram 1.0',
        'V_1_TURBO': 'Ideogram 1.0 Turbo',
    }

    DEFAULT_MODEL = 'V_2A_TURBO'  # Best for text overlays

    # Verfügbare Styles
    AVAILABLE_STYLES = {
        'REALISTIC': 'REALISTIC',
        'DESIGN': 'DESIGN',
        'RENDER_3D': 'RENDER_3D',
        'ANIME': 'ANIME',
        'GENERAL': 'GENERAL',
    }

    DEFAULT_STYLE = 'REALISTIC'

    def generate_image(self, prompt: str, reference_image=None, width: int = 1000, height: int = 1500, model: str = None, style: str = None) -> dict:
        """
        Generiert ein Bild mit Ideogram.ai

        Args:
            prompt: Beschreibung des gewünschten Bildes
            reference_image: Optional - Django ImageField oder Pfad zum Referenzbild
            width: Bildbreite
            height: Bildhöhe
            model: Ideogram Modell (V_2A_TURBO, V_2A, V_2, V_2_TURBO, V_1, V_1_TURBO)

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        # Use provided model or default
        selected_model = model if model and model in self.AVAILABLE_MODELS else self.DEFAULT_MODEL
        selected_style = style if style and style in self.AVAILABLE_STYLES else self.DEFAULT_STYLE
        logger.info(f"Using Ideogram model: {selected_model}, style: {selected_style}")

        try:
            # Determine aspect ratio
            aspect_ratio = self.ASPECT_RATIOS.get((width, height), "ASPECT_2_3")

            # Build the request payload
            payload = {
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": selected_model,
                    "style_type": selected_style,
                    "magic_prompt_option": "AUTO"
                }
            }

            # If reference image provided, use remix endpoint
            if reference_image:
                return self._generate_with_reference(prompt, reference_image, aspect_ratio, selected_model, selected_style)

            # Standard generation
            response = requests.post(
                f"{self.BASE_URL}/generate",
                headers=self.headers,
                json=payload,
                timeout=120  # 2 minute timeout for generation
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data") and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url")
                    if image_url:
                        # Download the image
                        img_response = requests.get(image_url, timeout=30)
                        if img_response.status_code == 200:
                            return {
                                'success': True,
                                'image_data': base64.b64encode(img_response.content).decode('utf-8')
                            }

                return {
                    'success': False,
                    'error': 'Keine Bilddaten in der Antwort'
                }
            else:
                error_msg = f"API Fehler: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
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
            logger.error(f"Error in Ideogram image generation: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_with_reference(self, prompt: str, reference_image, aspect_ratio: str, model: str = None, style: str = None) -> dict:
        """
        Generiert ein Bild mit Referenzbild (Remix)

        Args:
            prompt: Beschreibung
            reference_image: Django ImageField oder Pfad
            aspect_ratio: Aspect ratio string
            model: Ideogram Modell
            style: Ideogram Style
        """
        selected_model = model or self.DEFAULT_MODEL
        selected_style = style or self.DEFAULT_STYLE

        try:
            # Read the reference image
            if hasattr(reference_image, 'read'):
                # It's a file-like object
                image_data = reference_image.read()
                reference_image.seek(0)  # Reset for future reads
            elif hasattr(reference_image, 'path'):
                # It's a Django ImageField
                with open(reference_image.path, 'rb') as f:
                    image_data = f.read()
            else:
                # It's a path string
                with open(reference_image, 'rb') as f:
                    image_data = f.read()

            # Convert to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            # Use remix endpoint with reference
            import json as json_lib

            image_request = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "model": selected_model,
                "style_type": selected_style,
                "magic_prompt_option": "AUTO",
                "image_weight": 50  # Balance between prompt and reference
            }

            # Use multipart form for image upload
            files = {
                'image_file': ('reference.png', image_data, 'image/png')
            }

            data = {
                'image_request': json_lib.dumps(image_request)
            }

            # Try remix endpoint
            response = requests.post(
                f"{self.BASE_URL}/remix",
                headers={"Api-Key": self.api_key},
                files=files,
                data=data,
                timeout=120
            )

            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get("data") and len(resp_data["data"]) > 0:
                    image_url = resp_data["data"][0].get("url")
                    if image_url:
                        img_response = requests.get(image_url, timeout=30)
                        if img_response.status_code == 200:
                            return {
                                'success': True,
                                'image_data': base64.b64encode(img_response.content).decode('utf-8')
                            }

                return {
                    'success': False,
                    'error': 'Keine Bilddaten in der Remix-Antwort'
                }
            else:
                # Kein Fallback - Fehler melden
                error_msg = f"Remix-API Fehler: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
                logger.error(f"Remix failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except Exception as e:
            logger.error(f"Error in Ideogram remix generation: {e}")
            return {
                'success': False,
                'error': f"Fehler bei der Bildgenerierung mit Referenzbild: {str(e)}"
            }

    def get_available_models(self) -> list:
        """Gibt verfügbare Modelle zurück"""
        return [
            {"id": "V_2", "name": "Ideogram V2 (Latest)"},
            {"id": "V_1_TURBO", "name": "Ideogram V1 Turbo (Fast)"},
            {"id": "V_1", "name": "Ideogram V1"},
        ]

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
        Baut einen optimierten Prompt für Bildgenerierung MIT integriertem Text.

        Ideogram ist besonders gut darin, Text in Bilder zu integrieren.
        Diese Methode erstellt einen Prompt, der:
        - Das Produktbild (falls vorhanden) als Hauptelement beschreibt
        - Den Hintergrund als Setting beschreibt
        - Den Text als Teil des Designs integriert

        Args:
            background_description: Beschreibung des Hintergrunds
            overlay_text: Der Text, der im Bild erscheinen soll
            text_position: Position des Textes (top, center, bottom)
            text_style: Stil des Textes
            keywords: Zusätzliche Keywords für Kontext
            has_product_image: Ob ein Produktbild als Referenz übergeben wird

        Returns:
            Optimierter Prompt für Ideogram
        """
        # Position mapping für natürliche Sprache
        position_map = {
            'top': 'at the top of the image',
            'center': 'prominently in the center',
            'bottom': 'at the bottom of the image'
        }
        position_text = position_map.get(text_position, 'prominently displayed')

        # Style-Beschreibungen für verschiedene Text-Stile
        style_descriptions = {
            'modern': 'clean, modern typography with bold sans-serif font',
            'elegant': 'elegant, sophisticated serif typography',
            'playful': 'fun, playful hand-written style typography',
            'bold': 'bold, impactful typography that stands out',
            'minimal': 'minimalist, subtle typography',
            'vintage': 'vintage, retro-style typography',
        }
        style_desc = style_descriptions.get(text_style, style_descriptions['modern'])

        # Baue den optimierten Prompt
        prompt_parts = []

        # Wenn ein Produktbild vorhanden ist, beschreibe die Integration
        if has_product_image:
            prompt_parts.append(
                "Create a Pinterest pin design that prominently features the product from the reference image"
            )
            if background_description:
                prompt_parts.append(
                    f"Place the product on this background: {background_description.strip()}"
                )
        else:
            # Nur Hintergrund-Beschreibung
            if background_description:
                prompt_parts.append(background_description.strip())

        # Text-Integration (Ideograms Stärke!)
        if overlay_text:
            # Ideogram braucht den Text in Anführungszeichen für beste Ergebnisse
            # Betone kontrastreichen, gut lesbaren Text in Pinterest-optimierter Größe
            text_instruction = (
                f'The text "{overlay_text}" is displayed {position_text}, using {style_desc}. '
                f'The text must be large, bold and highly readable with strong contrast against the background. '
                f'Optimal text size for Pinterest pins.'
            )
            prompt_parts.append(text_instruction)

        # Zusätzliche Qualitäts-Keywords für Pinterest
        quality_keywords = [
            "Pinterest pin design",
            "high quality",
            "professional graphic design",
            "visually appealing",
            "eye-catching",
            "high contrast text",
            "clear readable typography"
        ]
        prompt_parts.extend(quality_keywords)

        # Kombiniere alles
        final_prompt = ". ".join(prompt_parts)

        logger.info(f"Built Ideogram prompt with text: {final_prompt[:150]}...")
        return final_prompt

    @staticmethod
    def build_prompt_without_text(
        background_description: str,
        keywords: str = '',
        has_product_image: bool = False
    ) -> str:
        """
        Baut einen Prompt für Bildgenerierung OHNE Text.
        Für Fälle, wo PIL-Overlay oder kein Text gewünscht ist.

        Args:
            background_description: Beschreibung des Hintergrunds
            keywords: Zusätzliche Keywords
            has_product_image: Ob ein Produktbild als Referenz übergeben wird

        Returns:
            Prompt für Ideogram ohne Text-Anweisungen
        """
        prompt_parts = []

        # Wenn ein Produktbild vorhanden ist, beschreibe die Integration
        if has_product_image:
            prompt_parts.append(
                "Create a Pinterest pin design that prominently features the product from the reference image"
            )
            if background_description:
                prompt_parts.append(
                    f"Place the product on this background: {background_description.strip()}"
                )
            prompt_parts.append("Leave space for text overlay")
        else:
            if background_description:
                prompt_parts.append(background_description.strip())

        # Pinterest-optimierte Keywords
        quality_keywords = [
            "Pinterest pin background",
            "high quality",
            "professional",
            "clean design",
            "space for text overlay"
        ]
        prompt_parts.extend(quality_keywords)

        final_prompt = ". ".join(prompt_parts)
        logger.info(f"Built Ideogram prompt without text: {final_prompt[:150]}...")
        return final_prompt

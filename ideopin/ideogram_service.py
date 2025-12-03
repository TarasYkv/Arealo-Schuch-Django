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

    def generate_image(self, prompt: str, reference_image=None, width: int = 1000, height: int = 1500) -> dict:
        """
        Generiert ein Bild mit Ideogram.ai

        Args:
            prompt: Beschreibung des gewünschten Bildes
            reference_image: Optional - Django ImageField oder Pfad zum Referenzbild
            width: Bildbreite
            height: Bildhöhe

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        try:
            # Determine aspect ratio
            aspect_ratio = self.ASPECT_RATIOS.get((width, height), "ASPECT_2_3")

            # Build the request payload
            payload = {
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": "V_2",  # Latest model
                    "magic_prompt_option": "AUTO"
                }
            }

            # If reference image provided, use remix endpoint
            if reference_image:
                return self._generate_with_reference(prompt, reference_image, aspect_ratio)

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

    def _generate_with_reference(self, prompt: str, reference_image, aspect_ratio: str) -> dict:
        """
        Generiert ein Bild mit Referenzbild (Remix)

        Args:
            prompt: Beschreibung
            reference_image: Django ImageField oder Pfad
            aspect_ratio: Aspect ratio string
        """
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
            payload = {
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": "V_2",
                    "magic_prompt_option": "AUTO",
                    "image_weight": 50  # Balance between prompt and reference
                },
                "image_file": image_b64
            }

            # Use multipart form for image upload
            files = {
                'image_file': ('reference.png', image_data, 'image/png')
            }

            data = {
                'image_request': str({
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": "V_2",
                    "magic_prompt_option": "AUTO"
                })
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
                # Fallback to standard generation if remix fails
                logger.warning(f"Remix failed with {response.status_code}, falling back to standard generation")
                return self._generate_standard(prompt, aspect_ratio)

        except Exception as e:
            logger.error(f"Error in Ideogram remix generation: {e}")
            # Fallback to standard generation
            return self._generate_standard(prompt, aspect_ratio)

    def _generate_standard(self, prompt: str, aspect_ratio: str) -> dict:
        """Fallback: Standard-Generierung ohne Referenzbild"""
        try:
            payload = {
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "model": "V_2",
                    "magic_prompt_option": "AUTO"
                }
            }

            response = requests.post(
                f"{self.BASE_URL}/generate",
                headers=self.headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data") and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url")
                    if image_url:
                        img_response = requests.get(image_url, timeout=30)
                        if img_response.status_code == 200:
                            return {
                                'success': True,
                                'image_data': base64.b64encode(img_response.content).decode('utf-8')
                            }

            return {
                'success': False,
                'error': 'Bildgenerierung fehlgeschlagen'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_available_models(self) -> list:
        """Gibt verfügbare Modelle zurück"""
        return [
            {"id": "V_2", "name": "Ideogram V2 (Latest)"},
            {"id": "V_1_TURBO", "name": "Ideogram V1 Turbo (Fast)"},
            {"id": "V_1", "name": "Ideogram V1"},
        ]

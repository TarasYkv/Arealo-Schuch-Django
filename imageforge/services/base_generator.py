"""
Abstrakte Basis-Klasse für Bild-Generatoren

Definiert das Interface für alle KI-Bild-Generatoren (Gemini, DALL-E, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseImageGenerator(ABC):
    """
    Abstrakte Basis-Klasse für alle Bild-Generatoren.

    Subklassen müssen implementieren:
    - generate(): Generiert ein Bild aus Prompt und optionalen Referenzbildern
    - get_available_models(): Gibt verfügbare Modelle zurück
    """

    def __init__(self, api_key: str):
        """
        Initialisiert den Generator mit einem API-Key.

        Args:
            api_key: Der API-Key für den jeweiligen Service
        """
        self.api_key = api_key

    @abstractmethod
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
        Generiert ein Bild basierend auf dem Prompt.

        Args:
            prompt: Der vollständige Prompt für die Bildgenerierung
            reference_images: Optional - Liste von Referenzbildern (Produkt/Charakter)
            width: Gewünschte Bildbreite
            height: Gewünschte Bildhöhe
            model: Spezifisches Modell (optional)
            quality: Qualitätsstufe ('standard', 'hd')

        Returns:
            Dict mit:
            - 'success': bool - Ob Generierung erfolgreich war
            - 'image_data': str - Base64-kodierte Bilddaten (bei Erfolg)
            - 'error': str - Fehlermeldung (bei Misserfolg)
            - 'model_used': str - Das verwendete Modell
        """
        pass

    @abstractmethod
    def get_available_models(self) -> Dict[str, str]:
        """
        Gibt die verfügbaren Modelle zurück.

        Returns:
            Dict mit Modell-ID als Key und Beschreibung als Value
            Beispiel: {'dall-e-3': 'DALL-E 3 - Beste Qualität'}
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name des Providers (z.B. 'OpenAI', 'Google')"""
        pass

    def validate_api_key(self) -> bool:
        """
        Prüft ob der API-Key gültig ist.

        Returns:
            True wenn Key vorhanden und nicht leer
        """
        return bool(self.api_key and len(self.api_key) > 10)

    def get_dimensions_for_ratio(self, aspect_ratio: str) -> tuple:
        """
        Konvertiert Aspect Ratio zu Pixel-Dimensionen.

        Args:
            aspect_ratio: Format wie '1:1', '16:9', etc.

        Returns:
            Tuple (width, height)
        """
        ratio_map = {
            '1:1': (1024, 1024),
            '4:3': (1024, 768),
            '3:4': (768, 1024),
            '16:9': (1024, 576),
            '9:16': (576, 1024),
        }
        return ratio_map.get(aspect_ratio, (1024, 1024))

    def _read_image_as_base64(self, image) -> Optional[str]:
        """
        Liest ein Bild und gibt es als Base64 zurück.

        Args:
            image: Datei-Objekt, Pfad oder Django FieldFile

        Returns:
            Base64-String oder None bei Fehler
        """
        import base64
        from django.core.files.base import ContentFile

        try:
            # Django FieldFile/ImageField - hat .path Attribut
            # Muss VOR read() geprüft werden, da FieldFile auch read() hat
            if hasattr(image, 'path') and not isinstance(image, ContentFile):
                try:
                    with open(image.path, 'rb') as f:
                        image_data = f.read()
                    return base64.b64encode(image_data).decode('utf-8')
                except Exception:
                    # Fallback: Versuche über read()
                    pass

            # ContentFile oder anderes file-like object
            if hasattr(image, 'read'):
                if hasattr(image, 'seek'):
                    try:
                        image.seek(0)
                    except Exception:
                        pass
                image_data = image.read()
                if hasattr(image, 'seek'):
                    try:
                        image.seek(0)
                    except Exception:
                        pass
                return base64.b64encode(image_data).decode('utf-8')

            # Pfad als String
            if isinstance(image, str):
                with open(image, 'rb') as f:
                    image_data = f.read()
                return base64.b64encode(image_data).decode('utf-8')

            logger.error(f"Unbekannter Bildtyp: {type(image)}")
            return None

        except Exception as e:
            logger.error(f"Error reading image: {e}")
            return None

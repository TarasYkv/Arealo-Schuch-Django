"""
P-Loom Image Service für Gravur-Workflow Bildgenerierung
Wrapper um GeminiImageService mit spezialisierten Prompts für Blumentopf-Gravuren
"""
import base64
import logging
import os
from datetime import datetime

from django.core.files.base import ContentFile

from ideopin.gemini_service import GeminiImageService, spell_out_text

logger = logging.getLogger(__name__)


class PLoomImageService:
    """Service für Gravur-Workflow Bildgenerierung"""

    def __init__(self, user):
        self.user = user
        self.settings = None
        self.gemini_service = None

        if user and user.is_authenticated:
            from ..models import PLoomSettings
            self.settings = PLoomSettings.objects.filter(user=user).first()

            api_key = user.gemini_api_key or getattr(user, 'google_api_key', None)
            if api_key:
                self.gemini_service = GeminiImageService(api_key=api_key)

    def generate_pot_image(self, engraving_text: str, scene_description: str, variant_type: str = 'komplett') -> dict:
        """
        Generiert ein Blumentopf-Produktbild mit Gravur.

        Args:
            engraving_text: Der Gravur-Text auf dem Topf
            scene_description: Beschreibung der Szene/Hintergrund
            variant_type: 'topf_nur' oder 'komplett'

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        if not self.gemini_service:
            return {'success': False, 'error': 'Gemini API-Key nicht konfiguriert'}

        # Gravur-Stil aus Settings
        engraving_style = 'elegante Schreibschrift'
        if self.settings and self.settings.engraving_style:
            engraving_style = self.settings.engraving_style

        # Buchstabiere den Gravur-Text für Genauigkeit
        spelled_text = spell_out_text(engraving_text)

        # Prompt bauen
        if variant_type == 'topf_nur':
            product_desc = (
                f"Ein wunderschöner handgefertigter Keramik-Blumentopf mit der Gravur "
                f"{spelled_text} in {engraving_style}. "
                f"Der Topf steht allein, ohne Zubehör."
            )
        else:
            komplett_desc = "Bio-Erde, Samen, Anleitung und Baumwollbeutel"
            if self.settings and self.settings.komplettset_description:
                komplett_desc = self.settings.komplettset_description
            product_desc = (
                f"Ein wunderschöner handgefertigter Keramik-Blumentopf mit der Gravur "
                f"{spelled_text} in {engraving_style}. "
                f"Daneben sichtbar: {komplett_desc}."
            )

        prompt = (
            f"Produktfoto, professionelle Beleuchtung, hohe Qualität. "
            f"{product_desc} "
            f"Szene: {scene_description}. "
            f"Die Gravur muss klar lesbar sein. "
            f"Warme, einladende Atmosphäre. "
            f"Quadratisches Format, weißer/heller Hintergrund-Akzent."
        )

        # Referenzbild aus Settings
        reference_image = None
        if self.settings and self.settings.reference_image:
            try:
                reference_image = self.settings.reference_image.path
            except Exception:
                pass

        # Modell aus Settings
        model = None
        if self.settings and self.settings.image_generation_model:
            model = self.settings.image_generation_model

        try:
            result = self.gemini_service.generate_image(
                prompt=prompt,
                reference_image=reference_image,
                width=1024,
                height=1024,
                model=model,
            )
            return result
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {'success': False, 'error': str(e)}

    def save_generated_image(self, image_base64: str, filename: str) -> str:
        """
        Speichert ein generiertes Bild als Datei.

        Args:
            image_base64: Base64-kodierte Bilddaten
            filename: Gewünschter Dateiname

        Returns:
            Relativer Dateipfad zum gespeicherten Bild
        """
        from django.conf import settings as django_settings

        now = datetime.now()
        rel_path = f"ploom/workflow_images/{now.year}/{now.month:02d}"
        full_dir = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        os.makedirs(full_dir, exist_ok=True)

        # Dateiname eindeutig machen
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = '.png'
        unique_filename = f"{base}_{now.strftime('%H%M%S')}{ext}"
        full_path = os.path.join(full_dir, unique_filename)

        # Speichern
        image_data = base64.b64decode(image_base64)
        with open(full_path, 'wb') as f:
            f.write(image_data)

        return f"{rel_path}/{unique_filename}"

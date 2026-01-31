"""
Image Processor für LoomMarket.
Bildverarbeitung und Mockup-Generierung.
"""
import io
import os
import logging
from typing import Optional, Tuple
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Verarbeitet Bilder für Gravur-Mockups.
    Konvertiert zu Graustufen/S/W für Lasergravur-Optik.
    """

    # Standard-Größen
    FEED_SIZE = (1080, 1080)  # Instagram Feed
    STORY_SIZE = (1080, 1920)  # Instagram Story (9:16)

    def __init__(self):
        pass

    def _open_image(self, image_file) -> Image.Image:
        """
        Öffnet ein Bild aus verschiedenen Quellen.

        Args:
            image_file: Django ImageField, FieldFile, ContentFile, File-like object oder Pfad

        Returns:
            PIL Image Objekt
        """
        # Django FieldFile/ImageField - hat .path Attribut
        if hasattr(image_file, 'path'):
            try:
                return Image.open(image_file.path)
            except Exception:
                # Fallback: Versuche über open() und read()
                if hasattr(image_file, 'open'):
                    image_file.open('rb')
                    img = Image.open(image_file)
                    return img
                raise

        # ContentFile oder anderes file-like object
        if hasattr(image_file, 'read'):
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            return Image.open(image_file)

        # String-Pfad
        if isinstance(image_file, str):
            return Image.open(image_file)

        raise ValueError(f"Kann Bild nicht öffnen: {type(image_file)}")

    def convert_to_grayscale(self, image_file) -> Optional[ContentFile]:
        """
        Konvertiert ein Bild zu Graustufen.
        Gut für realistische Gravur-Vorschauen.

        Args:
            image_file: Django ImageField oder File-like object

        Returns:
            ContentFile mit Graustufenbild oder None
        """
        try:
            # Bild öffnen
            img = self._open_image(image_file)

            # Zu RGB konvertieren (falls RGBA)
            if img.mode == 'RGBA':
                # Weißer Hintergrund für Transparenz
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Zu Graustufen konvertieren
            gray = ImageOps.grayscale(img)

            # Kontrast leicht erhöhen für bessere Gravur-Optik
            enhancer = ImageEnhance.Contrast(gray)
            gray = enhancer.enhance(1.2)

            # Als PNG speichern
            buffer = io.BytesIO()
            gray.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            return ContentFile(buffer.getvalue(), name='grayscale.png')

        except Exception as e:
            logger.exception(f"Error converting to grayscale: {e}")
            return None

    def convert_to_pure_bw(
        self,
        image_file,
        threshold: int = 128,
        invert: bool = False
    ) -> Optional[ContentFile]:
        """
        Konvertiert ein Bild zu reinem Schwarz/Weiß (1-Bit).
        Optimal für Lasergravur-Designs.

        Args:
            image_file: Django ImageField oder File-like object
            threshold: Schwellenwert für S/W (0-255)
            invert: True = invertiert (weiß auf schwarz)

        Returns:
            ContentFile mit S/W-Bild oder None
        """
        try:
            # Bild öffnen
            img = self._open_image(image_file)

            # Zu RGB konvertieren (falls RGBA)
            if img.mode == 'RGBA':
                # Weißer Hintergrund für Transparenz
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Zu Graustufen
            gray = ImageOps.grayscale(img)

            # Schwellenwert anwenden
            bw = gray.point(lambda x: 255 if x > threshold else 0, mode='1')

            # Optional invertieren
            if invert:
                bw = ImageOps.invert(bw.convert('L')).convert('1')

            # Als PNG speichern
            buffer = io.BytesIO()
            bw.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            return ContentFile(buffer.getvalue(), name='bw.png')

        except Exception as e:
            logger.exception(f"Error converting to B/W: {e}")
            return None

    def resize_for_feed(self, image_file) -> Optional[ContentFile]:
        """
        Skaliert Bild auf Instagram Feed-Größe (1080x1080).
        Behält Seitenverhältnis und füllt mit Weiß.
        """
        return self._resize_with_padding(image_file, self.FEED_SIZE)

    def resize_for_story(self, image_file) -> Optional[ContentFile]:
        """
        Skaliert Bild auf Instagram Story-Größe (1080x1920).
        Behält Seitenverhältnis und füllt mit Weiß.
        """
        return self._resize_with_padding(image_file, self.STORY_SIZE)

    def _resize_with_padding(
        self,
        image_file,
        target_size: Tuple[int, int],
        background_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Optional[ContentFile]:
        """
        Skaliert Bild und füllt mit Hintergrundfarbe.

        Args:
            image_file: Bilddatei
            target_size: (width, height)
            background_color: RGB-Farbe für Hintergrund

        Returns:
            ContentFile mit skaliertem Bild
        """
        try:
            # Bild öffnen
            img = self._open_image(image_file)

            # Zu RGB konvertieren
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, background_color)
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Skalierungsfaktor berechnen
            original_ratio = img.width / img.height
            target_ratio = target_size[0] / target_size[1]

            if original_ratio > target_ratio:
                # Bild ist breiter - nach Breite skalieren
                new_width = target_size[0]
                new_height = int(new_width / original_ratio)
            else:
                # Bild ist höher - nach Höhe skalieren
                new_height = target_size[1]
                new_width = int(new_height * original_ratio)

            # Skalieren mit hoher Qualität
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Neues Bild mit Hintergrund erstellen
            result = Image.new('RGB', target_size, background_color)

            # Zentriert einfügen
            x = (target_size[0] - new_width) // 2
            y = (target_size[1] - new_height) // 2
            result.paste(img, (x, y))

            # Als JPEG speichern (kleiner)
            buffer = io.BytesIO()
            result.save(buffer, format='JPEG', quality=95, optimize=True)
            buffer.seek(0)

            return ContentFile(buffer.getvalue(), name='resized.jpg')

        except Exception as e:
            logger.exception(f"Error resizing image: {e}")
            return None

    def prepare_design_for_mockup(
        self,
        design_image_file,
        convert_bw: bool = True,
        threshold: int = 128
    ) -> Optional[ContentFile]:
        """
        Bereitet ein Design-Bild für die Mockup-Generierung vor.

        Args:
            design_image_file: Bilddatei (Logo, Produktbild)
            convert_bw: True = zu S/W konvertieren
            threshold: Schwellenwert für S/W

        Returns:
            ContentFile mit vorbereitetem Bild
        """
        if convert_bw:
            return self.convert_to_pure_bw(design_image_file, threshold)
        else:
            return self.convert_to_grayscale(design_image_file)


class MockupGenerator:
    """
    Generiert Produkt-Mockups mit dem ImageForge GeminiGenerator.
    """

    def __init__(self, user):
        """
        Args:
            user: Django User für API-Key
        """
        self.user = user
        self.image_processor = ImageProcessor()

    def generate_mockup(
        self,
        template,
        design_image,
        background_prompt: str = None,
        generate_story: bool = True
    ) -> dict:
        """
        Generiert ein Mockup mit KI.

        Args:
            template: MockupTemplate instance
            design_image: BusinessImage oder ImageField
            background_prompt: Optionale Hintergrundbeschreibung
            generate_story: True = auch Story-Format generieren

        Returns:
            Dict mit 'feed_image' und optional 'story_image'
        """
        result = {
            'success': False,
            'feed_image': None,
            'story_image': None,
            'error': None,
        }

        try:
            # ImageForge GeminiGenerator importieren
            from imageforge.services.gemini_generator import GeminiGenerator

            # API-Key vom User holen
            api_key = getattr(self.user, 'gemini_api_key', None)
            if not api_key:
                result['error'] = 'Gemini API-Key nicht konfiguriert. Bitte in den Einstellungen hinterlegen.'
                return result

            # Generator initialisieren
            generator = GeminiGenerator(api_key)

            # Design-Bild vorbereiten (S/W für Gravur)
            design_file = design_image.image if hasattr(design_image, 'image') else design_image
            prepared_design = self.image_processor.convert_to_pure_bw(design_file)

            if not prepared_design:
                result['error'] = "Fehler bei der Bildvorbereitung"
                return result

            # Prompt für Mockup-Generierung
            prompt = self._build_mockup_prompt(
                template,
                background_prompt or template.default_background_prompt
            )

            # Feed-Bild generieren (1:1)
            logger.info("Generating feed mockup...")
            feed_result = generator.generate(
                prompt=prompt,
                reference_images=[
                    template.product_image_blank,
                    template.product_image_engraved,
                    prepared_design,
                ],
                width=1024,
                height=1024,
            )

            if feed_result.get('success') and feed_result.get('image_data'):
                result['feed_image'] = feed_result['image_data']
            else:
                result['error'] = feed_result.get('error', 'Mockup-Generierung fehlgeschlagen')
                return result

            # Story-Bild generieren (9:16)
            if generate_story:
                logger.info("Generating story mockup...")
                story_result = generator.generate(
                    prompt=prompt,
                    reference_images=[
                        template.product_image_blank,
                        template.product_image_engraved,
                        prepared_design,
                    ],
                    width=1024,
                    height=1820,  # 9:16 ratio
                )

                if story_result.get('success') and story_result.get('image_data'):
                    result['story_image'] = story_result['image_data']
                # Story-Fehler ist nicht kritisch

            result['success'] = True
            logger.info("Mockup generation completed successfully")

        except ImportError:
            result['error'] = "ImageForge nicht verfügbar"
            logger.error("ImageForge GeminiGenerator not available")
        except Exception as e:
            result['error'] = f"Generierungsfehler: {str(e)}"
            logger.exception(f"Error generating mockup: {e}")

        return result

    def _build_mockup_prompt(self, template, background_prompt: str = None) -> str:
        """
        Erstellt den Prompt für die Mockup-Generierung.

        Args:
            template: MockupTemplate instance
            background_prompt: Optionale Hintergrundbeschreibung

        Returns:
            Prompt-String
        """
        base_prompt = (
            f"Generiere ein professionelles Produktfoto von einem {template.name}. "
            f"WICHTIG: Das dritte Referenzbild zeigt das Design/Logo, das als Lasergravur auf dem Produkt erscheinen soll. "
            f"Das KOMPLETTE Design muss vollständig sichtbar sein - schneide NICHTS ab! "
            f"Skaliere das Design so, dass es gut auf das Produkt passt und zentriert ist. "
            f"Verwende das erste Referenzbild (Produkt ohne Gravur) als Basis für Form und Perspektive. "
            f"Verwende das zweite Referenzbild als Beispiel für den Gravur-Stil (Tiefe, Schattierung, Textur). "
            f"Die Gravur soll realistisch, hochwertig und gut lesbar aussehen."
        )

        if background_prompt:
            base_prompt += f" Der Hintergrund: {background_prompt}"
        else:
            base_prompt += " Verwende einen neutralen, professionellen Hintergrund."

        return base_prompt

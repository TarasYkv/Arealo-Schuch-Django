"""
Slogan Image Generator für LoomMarket.
Erstellt Slogan-Bilder mit Google Fonts für Gravur-Optionen.
"""
import io
import os
import logging
import requests
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Dict, List, Tuple
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class SloganImageGenerator:
    """
    Generiert Slogan-Bilder mit verschiedenen Google Fonts.
    Die Bilder sind für Gravur-Zwecke optimiert (S/W, hoher Kontrast).
    """

    # Google Fonts die gut für Gravuren geeignet sind (dekorativ, gut lesbar)
    AVAILABLE_FONTS = {
        'playfair': {
            'name': 'Playfair Display',
            'url': 'https://github.com/googlefonts/Playfair/raw/main/fonts/ttf/PlayfairDisplay-Bold.ttf',
            'style': 'Elegant Serif',
            'description': 'Elegante Serifenschrift - klassisch und edel'
        },
        'dancing_script': {
            'name': 'Dancing Script',
            'url': 'https://github.com/impallari/DancingScript/raw/master/fonts/DancingScript-Bold.ttf',
            'style': 'Handschrift',
            'description': 'Fließende Handschrift - persönlich und warm'
        },
        'oswald': {
            'name': 'Oswald',
            'url': 'https://github.com/googlefonts/OswaldFont/raw/main/fonts/ttf/Oswald-Bold.ttf',
            'style': 'Modern Sans',
            'description': 'Moderne Sans-Serif - klar und kraftvoll'
        },
        'great_vibes': {
            'name': 'Great Vibes',
            'url': 'https://github.com/nickmass/Great-Vibes/raw/master/GreatVibes-Regular.ttf',
            'style': 'Kalligrafie',
            'description': 'Kalligrafische Schrift - feierlich und festlich'
        },
        'bebas_neue': {
            'name': 'Bebas Neue',
            'url': 'https://github.com/dharmatype/Bebas-Neue/raw/master/fonts/BebasNeue-Regular.ttf',
            'style': 'Display',
            'description': 'Markante Versalien - modern und auffällig'
        },
        'pacifico': {
            'name': 'Pacifico',
            'url': 'https://github.com/googlefonts/Pacifico/raw/main/fonts/Pacifico-Regular.ttf',
            'style': 'Retro Script',
            'description': 'Retro-Schreibschrift - freundlich und verspielt'
        },
        'cinzel': {
            'name': 'Cinzel',
            'url': 'https://github.com/googlefonts/Cinzel/raw/main/fonts/ttf/Cinzel-Bold.ttf',
            'style': 'Klassisch',
            'description': 'Klassische Kapitälchen - zeitlos und würdevoll'
        },
        'montserrat': {
            'name': 'Montserrat',
            'url': 'https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf',
            'style': 'Geometric Sans',
            'description': 'Geometrische Sans-Serif - clean und professionell'
        },
    }

    # Standard Bildgröße für Gravur-Vorlagen
    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 400

    # Schriftfarben für Gravur (S/W)
    TEXT_COLOR = (0, 0, 0)  # Schwarz
    BG_COLOR = (255, 255, 255)  # Weiß

    def __init__(self):
        """Initialisiert den Generator und lädt Fonts."""
        self.fonts_dir = Path(settings.MEDIA_ROOT) / 'loommarket' / 'fonts'
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        self._cached_fonts: Dict[str, ImageFont.FreeTypeFont] = {}
        logger.info("SloganImageGenerator initialized")

    def get_available_fonts(self) -> List[Dict]:
        """
        Gibt Liste der verfügbaren Fonts zurück.

        Returns:
            Liste mit Font-Infos (id, name, style, description)
        """
        return [
            {
                'id': font_id,
                'name': info['name'],
                'style': info['style'],
                'description': info['description']
            }
            for font_id, info in self.AVAILABLE_FONTS.items()
        ]

    def _download_font(self, font_id: str) -> Optional[Path]:
        """
        Lädt einen Font von Google Fonts herunter.

        Args:
            font_id: ID des Fonts

        Returns:
            Pfad zur Font-Datei oder None bei Fehler
        """
        if font_id not in self.AVAILABLE_FONTS:
            logger.error(f"Unknown font: {font_id}")
            return None

        font_info = self.AVAILABLE_FONTS[font_id]
        font_path = self.fonts_dir / f"{font_id}.ttf"

        # Font bereits heruntergeladen?
        if font_path.exists():
            return font_path

        try:
            logger.info(f"Downloading font: {font_info['name']}")
            response = requests.get(font_info['url'], timeout=30)
            response.raise_for_status()

            font_path.write_bytes(response.content)
            logger.info(f"Font downloaded: {font_path}")
            return font_path

        except Exception as e:
            logger.error(f"Error downloading font {font_id}: {e}")
            return None

    def _get_font(self, font_id: str, size: int = 60) -> Optional[ImageFont.FreeTypeFont]:
        """
        Lädt einen Font in der gewünschten Größe.

        Args:
            font_id: ID des Fonts
            size: Schriftgröße in Pixeln

        Returns:
            PIL ImageFont oder None
        """
        cache_key = f"{font_id}_{size}"

        if cache_key in self._cached_fonts:
            return self._cached_fonts[cache_key]

        font_path = self._download_font(font_id)
        if not font_path:
            # Fallback auf System-Font
            logger.warning(f"Using default font as fallback for {font_id}")
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            except:
                return ImageFont.load_default()

        try:
            font = ImageFont.truetype(str(font_path), size)
            self._cached_fonts[cache_key] = font
            return font
        except Exception as e:
            logger.error(f"Error loading font {font_id}: {e}")
            return ImageFont.load_default()

    def _calculate_font_size(
        self,
        text: str,
        font_id: str,
        max_width: int,
        max_height: int,
        padding: int = 40
    ) -> int:
        """
        Berechnet die optimale Schriftgröße für den Text.

        Args:
            text: Der zu rendernde Text
            font_id: ID des Fonts
            max_width: Maximale Breite
            max_height: Maximale Höhe
            padding: Rand in Pixeln

        Returns:
            Optimale Schriftgröße
        """
        available_width = max_width - (padding * 2)
        available_height = max_height - (padding * 2)

        # Starte mit großer Schrift und verkleinere
        for size in range(120, 20, -4):
            font = self._get_font(font_id, size)
            if not font:
                continue

            # Text-Bounding-Box ermitteln
            dummy_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(dummy_img)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if text_width <= available_width and text_height <= available_height:
                return size

        return 24  # Minimum

    def generate_slogan_image(
        self,
        text: str,
        font_id: str = 'playfair',
        width: int = None,
        height: int = None,
        inverted: bool = False
    ) -> Optional[Dict]:
        """
        Generiert ein Slogan-Bild mit dem angegebenen Font.

        Args:
            text: Slogan-Text
            font_id: ID des Fonts (aus AVAILABLE_FONTS)
            width: Bildbreite (optional)
            height: Bildhöhe (optional)
            inverted: True für weißen Text auf schwarzem Grund

        Returns:
            Dict mit image (ContentFile), width, height, font_name
        """
        if not text or not text.strip():
            logger.warning("Empty text provided")
            return None

        text = text.strip()
        width = width or self.DEFAULT_WIDTH
        height = height or self.DEFAULT_HEIGHT

        # Farben
        bg_color = self.TEXT_COLOR if inverted else self.BG_COLOR
        text_color = self.BG_COLOR if inverted else self.TEXT_COLOR

        try:
            # Optimale Schriftgröße berechnen
            font_size = self._calculate_font_size(text, font_id, width, height)
            font = self._get_font(font_id, font_size)

            if not font:
                logger.error(f"Could not load font: {font_id}")
                return None

            # Bild erstellen
            img = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)

            # Text-Position berechnen (zentriert)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (width - text_width) // 2
            y = (height - text_height) // 2 - bbox[1]  # Korrektur für Baseline

            # Text zeichnen
            draw.text((x, y), text, font=font, fill=text_color)

            # Als PNG speichern
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            # Eindeutigen Dateinamen generieren
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"slogan_{font_id}_{text_hash}.png"

            font_name = self.AVAILABLE_FONTS.get(font_id, {}).get('name', font_id)

            logger.info(f"Generated slogan image: {filename} ({width}x{height}, font: {font_name})")

            return {
                'image': ContentFile(buffer.read(), name=filename),
                'width': width,
                'height': height,
                'font_id': font_id,
                'font_name': font_name,
                'text': text,
                'inverted': inverted,
            }

        except Exception as e:
            logger.exception(f"Error generating slogan image: {e}")
            return None

    def generate_all_font_previews(
        self,
        text: str,
        width: int = None,
        height: int = None
    ) -> List[Dict]:
        """
        Generiert Vorschaubilder für alle verfügbaren Fonts.

        Args:
            text: Slogan-Text
            width: Bildbreite (optional)
            height: Bildhöhe (optional)

        Returns:
            Liste mit generierten Bildern
        """
        previews = []

        for font_id in self.AVAILABLE_FONTS:
            result = self.generate_slogan_image(text, font_id, width, height)
            if result:
                previews.append(result)

        logger.info(f"Generated {len(previews)} font previews for slogan")
        return previews

    def generate_slogan_for_engraving(
        self,
        text: str,
        font_id: str = 'playfair'
    ) -> Optional[Dict]:
        """
        Generiert ein Slogan-Bild optimiert für Gravur.
        Quadratisches Format, hoher Kontrast, reines S/W.

        Args:
            text: Slogan-Text
            font_id: ID des Fonts

        Returns:
            Dict mit Bilddaten
        """
        # Quadratisches Format für Gravur
        size = 600
        return self.generate_slogan_image(
            text=text,
            font_id=font_id,
            width=size,
            height=size,
            inverted=False  # Schwarz auf Weiß für Gravur
        )

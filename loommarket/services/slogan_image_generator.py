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

    # Google Fonts - Große Auswahl an Schreibschriften und dekorativen Fonts
    AVAILABLE_FONTS = {
        # ========== ELEGANTE SCHREIBSCHRIFTEN ==========
        'great_vibes': {
            'name': 'Great Vibes',
            'url': 'https://github.com/nickmass/Great-Vibes/raw/master/GreatVibes-Regular.ttf',
            'style': 'Elegante Kalligrafie',
            'category': 'script',
            'description': 'Festliche kalligrafische Schrift'
        },
        'alex_brush': {
            'name': 'Alex Brush',
            'url': 'https://github.com/googlefonts/alex-brush/raw/main/fonts/ttf/AlexBrush-Regular.ttf',
            'style': 'Brush Script',
            'category': 'script',
            'description': 'Elegante Pinselschrift'
        },
        'allura': {
            'name': 'Allura',
            'url': 'https://github.com/nickmass/Allura/raw/master/Allura-Regular.ttf',
            'style': 'Formale Schreibschrift',
            'category': 'script',
            'description': 'Formelle elegante Schreibschrift'
        },
        'pinyon_script': {
            'name': 'Pinyon Script',
            'url': 'https://github.com/nickmass/Pinyon-Script/raw/master/PinyonScript-Regular.ttf',
            'style': 'Klassische Kalligrafie',
            'category': 'script',
            'description': 'Klassische Federschrift'
        },
        'tangerine': {
            'name': 'Tangerine',
            'url': 'https://github.com/nickmass/Tangerine/raw/master/Tangerine-Bold.ttf',
            'style': 'Feine Schreibschrift',
            'category': 'script',
            'description': 'Zarte elegante Linien'
        },
        'rouge_script': {
            'name': 'Rouge Script',
            'url': 'https://github.com/nickmass/Rouge-Script/raw/master/RougeScript-Regular.ttf',
            'style': 'Vintage Script',
            'category': 'script',
            'description': 'Vintage-Eleganz'
        },
        'italianno': {
            'name': 'Italianno',
            'url': 'https://github.com/nickmass/Italianno/raw/master/Italianno-Regular.ttf',
            'style': 'Italienische Kalligrafie',
            'category': 'script',
            'description': 'Fließende italienische Schrift'
        },
        'corinthia': {
            'name': 'Corinthia',
            'url': 'https://github.com/nickmass/Corinthia/raw/main/fonts/ttf/Corinthia-Bold.ttf',
            'style': 'Moderne Kalligrafie',
            'category': 'script',
            'description': 'Moderne elegante Kalligrafie'
        },

        # ========== HANDSCHRIFTEN ==========
        'dancing_script': {
            'name': 'Dancing Script',
            'url': 'https://github.com/impallari/DancingScript/raw/master/fonts/DancingScript-Bold.ttf',
            'style': 'Fröhliche Handschrift',
            'category': 'handwriting',
            'description': 'Lebendige Handschrift'
        },
        'sacramento': {
            'name': 'Sacramento',
            'url': 'https://github.com/nickmass/Sacramento/raw/master/Sacramento-Regular.ttf',
            'style': 'Lässige Schreibschrift',
            'category': 'handwriting',
            'description': 'Entspannte Monoline-Schrift'
        },
        'satisfy': {
            'name': 'Satisfy',
            'url': 'https://github.com/nickmass/Satisfy/raw/master/Satisfy-Regular.ttf',
            'style': 'Retro Handschrift',
            'category': 'handwriting',
            'description': '50er Jahre Stil'
        },
        'kaushan_script': {
            'name': 'Kaushan Script',
            'url': 'https://github.com/googlefonts/kaushan-script/raw/main/fonts/ttf/KaushanScript-Regular.ttf',
            'style': 'Pinsel-Handschrift',
            'category': 'handwriting',
            'description': 'Kraftvolle Pinselschrift'
        },
        'marck_script': {
            'name': 'Marck Script',
            'url': 'https://github.com/nickmass/Marck-Script/raw/master/MarckScript-Regular.ttf',
            'style': 'Moderne Handschrift',
            'category': 'handwriting',
            'description': 'Zeitgenössische Handschrift'
        },
        'cookie': {
            'name': 'Cookie',
            'url': 'https://github.com/nickmass/Cookie/raw/master/Cookie-Regular.ttf',
            'style': 'Verspielte Schrift',
            'category': 'handwriting',
            'description': 'Süße verspielte Handschrift'
        },
        'courgette': {
            'name': 'Courgette',
            'url': 'https://github.com/nickmass/Courgette/raw/master/Courgette-Regular.ttf',
            'style': 'Brush Handschrift',
            'category': 'handwriting',
            'description': 'Weiche Pinselschrift'
        },
        'niconne': {
            'name': 'Niconne',
            'url': 'https://github.com/nickmass/Niconne/raw/master/Niconne-Regular.ttf',
            'style': 'Elegante Handschrift',
            'category': 'handwriting',
            'description': 'Stilvolle Handschrift'
        },
        'euphoria_script': {
            'name': 'Euphoria Script',
            'url': 'https://github.com/nickmass/Euphoria-Script/raw/master/EuphoriaScript-Regular.ttf',
            'style': 'Fließende Handschrift',
            'category': 'handwriting',
            'description': 'Weiche fließende Linien'
        },

        # ========== AUSGEFALLENE DISPLAY-FONTS ==========
        'lobster': {
            'name': 'Lobster',
            'url': 'https://github.com/impallari/Lobster/raw/master/static/Lobster-Regular.ttf',
            'style': 'Bold Script',
            'category': 'display',
            'description': 'Kräftige Retro-Schreibschrift'
        },
        'pacifico': {
            'name': 'Pacifico',
            'url': 'https://github.com/googlefonts/Pacifico/raw/main/fonts/Pacifico-Regular.ttf',
            'style': 'Surf Retro',
            'category': 'display',
            'description': 'Kalifornischer Surf-Stil'
        },
        'yellowtail': {
            'name': 'Yellowtail',
            'url': 'https://github.com/nickmass/Yellowtail/raw/master/Yellowtail-Regular.ttf',
            'style': 'Vintage Script',
            'category': 'display',
            'description': 'Amerikanischer Retro-Stil'
        },
        'berkshire_swash': {
            'name': 'Berkshire Swash',
            'url': 'https://github.com/nickmass/Berkshire-Swash/raw/master/BerkshireSwash-Regular.ttf',
            'style': 'Swash Display',
            'category': 'display',
            'description': 'Elegante Schwünge'
        },
        'arizonia': {
            'name': 'Arizonia',
            'url': 'https://github.com/nickmass/Arizonia/raw/master/Arizonia-Regular.ttf',
            'style': 'Western Eleganz',
            'category': 'display',
            'description': 'Eleganter Western-Stil'
        },
        'clicker_script': {
            'name': 'Clicker Script',
            'url': 'https://github.com/nickmass/Clicker-Script/raw/master/ClickerScript-Regular.ttf',
            'style': 'Formale Display',
            'category': 'display',
            'description': 'Formelle Display-Schrift'
        },
        'lovers_quarrel': {
            'name': 'Lovers Quarrel',
            'url': 'https://github.com/nickmass/Lovers-Quarrel/raw/master/LoversQuarrel-Regular.ttf',
            'style': 'Romantisch',
            'category': 'display',
            'description': 'Romantische Schnörkel'
        },
        'mr_de_haviland': {
            'name': 'Mr De Haviland',
            'url': 'https://github.com/nickmass/Mr-De-Haviland/raw/master/MrDeHaviland-Regular.ttf',
            'style': 'Gentleman Script',
            'category': 'display',
            'description': 'Vornehme Signatur'
        },
        'herr_von_muellerhoff': {
            'name': 'Herr Von Muellerhoff',
            'url': 'https://github.com/nickmass/Herr-Von-Muellerhoff/raw/master/HerrVonMuellerhoff-Regular.ttf',
            'style': 'Aristokratisch',
            'category': 'display',
            'description': 'Aristokratische Eleganz'
        },
        'monsieur_la_doulaise': {
            'name': 'Monsieur La Doulaise',
            'url': 'https://github.com/nickmass/Monsieur-La-Doulaise/raw/master/MonsieurLaDoulaise-Regular.ttf',
            'style': 'Französisch Elegant',
            'category': 'display',
            'description': 'Französische Raffinesse'
        },

        # ========== GOTHIC & DEKORATIV ==========
        'cinzel_decorative': {
            'name': 'Cinzel Decorative',
            'url': 'https://github.com/googlefonts/CinzelDecorative/raw/main/fonts/ttf/CinzelDecorative-Bold.ttf',
            'style': 'Dekorative Kapitälchen',
            'category': 'decorative',
            'description': 'Verzierte römische Kapitälchen'
        },
        'unifraktur': {
            'name': 'UnifrakturMaguntia',
            'url': 'https://github.com/googlefonts/unifraktur/raw/main/fonts/ttf/UnifrakturMaguntia-Regular.ttf',
            'style': 'Fraktur/Gothic',
            'category': 'decorative',
            'description': 'Deutsche Frakturschrift'
        },
        'almendra_display': {
            'name': 'Almendra Display',
            'url': 'https://github.com/nickmass/Almendra/raw/master/Almendra-Display.ttf',
            'style': 'Mittelalterlich',
            'category': 'decorative',
            'description': 'Mittelalterlicher Fantasy-Stil'
        },
        'uncial_antiqua': {
            'name': 'Uncial Antiqua',
            'url': 'https://github.com/nickmass/Uncial-Antiqua/raw/master/UncialAntiqua-Regular.ttf',
            'style': 'Unziale',
            'category': 'decorative',
            'description': 'Keltisch-mittelalterlich'
        },

        # ========== MODERNE & CLEAN ==========
        'playfair': {
            'name': 'Playfair Display',
            'url': 'https://github.com/googlefonts/Playfair/raw/main/fonts/ttf/PlayfairDisplay-Bold.ttf',
            'style': 'Elegant Modern',
            'category': 'modern',
            'description': 'Elegante Serifenschrift'
        },
        'cinzel': {
            'name': 'Cinzel',
            'url': 'https://github.com/googlefonts/Cinzel/raw/main/fonts/ttf/Cinzel-Bold.ttf',
            'style': 'Klassisch',
            'category': 'modern',
            'description': 'Zeitlose Kapitälchen'
        },
        'bebas_neue': {
            'name': 'Bebas Neue',
            'url': 'https://github.com/dharmatype/Bebas-Neue/raw/master/fonts/BebasNeue-Regular.ttf',
            'style': 'Bold Display',
            'category': 'modern',
            'description': 'Markante Versalien'
        },
        'oswald': {
            'name': 'Oswald',
            'url': 'https://github.com/googlefonts/OswaldFont/raw/main/fonts/ttf/Oswald-Bold.ttf',
            'style': 'Modern Sans',
            'category': 'modern',
            'description': 'Klare moderne Sans-Serif'
        },
        'montserrat': {
            'name': 'Montserrat',
            'url': 'https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf',
            'style': 'Geometric',
            'category': 'modern',
            'description': 'Geometrische Sans-Serif'
        },
        'abril_fatface': {
            'name': 'Abril Fatface',
            'url': 'https://github.com/nickmass/Abril-Fatface/raw/master/AbrilFatface-Regular.ttf',
            'style': 'Display Serif',
            'category': 'modern',
            'description': 'Elegante Display-Schrift'
        },
        'poiret_one': {
            'name': 'Poiret One',
            'url': 'https://github.com/nickmass/Poiret-One/raw/master/PoiretOne-Regular.ttf',
            'style': 'Art Deco',
            'category': 'modern',
            'description': 'Art Deco Eleganz'
        },
        'comfortaa': {
            'name': 'Comfortaa',
            'url': 'https://github.com/nickmass/Comfortaa/raw/master/fonts/Comfortaa-Bold.ttf',
            'style': 'Rounded Modern',
            'category': 'modern',
            'description': 'Weiche abgerundete Schrift'
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

    # Kategorien mit deutschen Namen
    CATEGORY_NAMES = {
        'script': 'Elegante Schreibschriften',
        'handwriting': 'Handschriften',
        'display': 'Ausgefallene Display-Fonts',
        'decorative': 'Gothic & Dekorativ',
        'modern': 'Modern & Clean',
    }

    def get_available_fonts(self) -> List[Dict]:
        """
        Gibt Liste der verfügbaren Fonts zurück, sortiert nach Kategorie.

        Returns:
            Liste mit Font-Infos (id, name, style, category, description)
        """
        fonts = [
            {
                'id': font_id,
                'name': info['name'],
                'style': info['style'],
                'category': info.get('category', 'modern'),
                'category_name': self.CATEGORY_NAMES.get(info.get('category', 'modern'), 'Sonstige'),
                'description': info['description']
            }
            for font_id, info in self.AVAILABLE_FONTS.items()
        ]

        # Sortieren nach Kategorie-Reihenfolge
        category_order = ['script', 'handwriting', 'display', 'decorative', 'modern']
        fonts.sort(key=lambda f: (category_order.index(f['category']) if f['category'] in category_order else 99, f['name']))

        return fonts

    def get_fonts_by_category(self) -> Dict[str, List[Dict]]:
        """
        Gibt Fonts gruppiert nach Kategorie zurück.

        Returns:
            Dict mit Kategorie als Key und Liste von Fonts als Value
        """
        fonts = self.get_available_fonts()
        grouped = {}

        for font in fonts:
            cat = font['category_name']
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(font)

        return grouped

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

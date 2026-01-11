"""
Thumbnail-Utility für Workloom

Generiert optimierte Thumbnails für schnelleres Laden von Bildergalerien.
Unterstützt WebP-Format für bessere Kompression.
"""

import os
import logging
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

# Thumbnail-Konfiguration
THUMBNAIL_SIZES = {
    'small': (200, 200),    # Für kleine Vorschauen
    'medium': (400, 400),   # Für Listen/Galerien
    'large': (800, 800),    # Für größere Ansichten
}

THUMBNAIL_QUALITY = 85  # WebP Qualität (0-100)
THUMBNAIL_FORMAT = 'WEBP'


def get_thumbnail_path(original_path: str, size: str = 'medium') -> str:
    """
    Generiert den Pfad für ein Thumbnail basierend auf dem Original.

    Args:
        original_path: Pfad zum Originalbild
        size: Größe des Thumbnails ('small', 'medium', 'large')

    Returns:
        Pfad zum Thumbnail
    """
    if not original_path:
        return ''

    # Verzeichnis und Dateiname trennen
    directory = os.path.dirname(original_path)
    filename = os.path.basename(original_path)
    name, _ = os.path.splitext(filename)

    # Thumbnail-Verzeichnis erstellen
    thumb_dir = os.path.join(directory, 'thumbnails')

    # Thumbnail-Dateiname
    thumb_filename = f"{name}_{size}.webp"

    return os.path.join(thumb_dir, thumb_filename)


def generate_thumbnail(image_field, size: str = 'medium', force: bool = False) -> str:
    """
    Generiert ein Thumbnail für ein ImageField.

    Args:
        image_field: Django ImageField
        size: Größe des Thumbnails ('small', 'medium', 'large')
        force: Thumbnail neu generieren auch wenn es existiert

    Returns:
        URL zum Thumbnail oder leerer String bei Fehler
    """
    if not image_field or not image_field.name:
        return ''

    try:
        # Thumbnail-Pfad bestimmen
        thumb_path = get_thumbnail_path(image_field.name, size)

        # Prüfen ob Thumbnail bereits existiert
        if not force and default_storage.exists(thumb_path):
            return default_storage.url(thumb_path)

        # Originalbild laden
        image_field.seek(0)
        img = Image.open(image_field)

        # RGBA zu RGB konvertieren falls nötig
        if img.mode in ('RGBA', 'P'):
            # Weißer Hintergrund für Transparenz
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Thumbnail-Größe bestimmen
        max_size = THUMBNAIL_SIZES.get(size, THUMBNAIL_SIZES['medium'])

        # Aspect Ratio beibehalten
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # In WebP speichern
        thumb_io = BytesIO()
        img.save(thumb_io, format=THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY, optimize=True)
        thumb_io.seek(0)

        # Thumbnail speichern
        default_storage.save(thumb_path, ContentFile(thumb_io.read()))

        logger.info(f"Thumbnail generiert: {thumb_path}")
        return default_storage.url(thumb_path)

    except Exception as e:
        logger.error(f"Fehler beim Generieren des Thumbnails: {e}")
        # Fallback zum Original
        return image_field.url if image_field else ''


def get_or_create_thumbnail(image_field, size: str = 'medium') -> str:
    """
    Gibt die URL eines Thumbnails zurück, generiert es bei Bedarf.

    Args:
        image_field: Django ImageField
        size: Größe des Thumbnails ('small', 'medium', 'large')

    Returns:
        URL zum Thumbnail
    """
    if not image_field or not image_field.name:
        return ''

    try:
        thumb_path = get_thumbnail_path(image_field.name, size)

        # Thumbnail existiert bereits
        if default_storage.exists(thumb_path):
            return default_storage.url(thumb_path)

        # Thumbnail generieren
        return generate_thumbnail(image_field, size)

    except Exception as e:
        logger.error(f"Fehler bei get_or_create_thumbnail: {e}")
        return image_field.url if image_field else ''


def delete_thumbnails(image_path: str) -> None:
    """
    Löscht alle Thumbnails für ein Bild.

    Args:
        image_path: Pfad zum Originalbild
    """
    if not image_path:
        return

    for size in THUMBNAIL_SIZES.keys():
        try:
            thumb_path = get_thumbnail_path(image_path, size)
            if default_storage.exists(thumb_path):
                default_storage.delete(thumb_path)
                logger.info(f"Thumbnail gelöscht: {thumb_path}")
        except Exception as e:
            logger.error(f"Fehler beim Löschen des Thumbnails: {e}")

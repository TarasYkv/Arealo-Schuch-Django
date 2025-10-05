"""
Organization Storage Tracking Signals
======================================
Trackt Image-Uploads und Deletions im globalen Storage-System
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Note, IdeaBoard, BoardElement
from core.storage_service import StorageService
from django.core.files.storage import default_storage
import logging
import os
import re

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Note)
def track_note_image_upload(sender, instance, created, **kwargs):
    """
    Trackt Image-Upload in Note
    Wird ausgeführt nach Note.save()
    """
    # Prüfe ob ein Bild existiert
    if instance.image and instance.image.name:
        try:
            # Hole Dateigröße aus ImageField
            file_size = instance.image.size if hasattr(instance.image, 'size') else 0

            if file_size > 0 and created:
                # Nur bei neuen Notes mit Bildern tracken
                StorageService.track_upload(
                    user=instance.author,
                    file_size=file_size,
                    app_name='organization',
                    metadata={
                        'note_id': instance.id,
                        'note_title': instance.title,
                        'filename': os.path.basename(instance.image.name),
                    }
                )
                logger.info(
                    f"Tracked organization image upload: {os.path.basename(instance.image.name)} "
                    f"({file_size} bytes) for user {instance.author.username}"
                )
        except Exception as e:
            # Bei Storage-Fehler loggen aber nicht blockieren
            logger.error(f"Failed to track organization image upload: {str(e)}")


@receiver(pre_delete, sender=Note)
def track_note_image_deletion(sender, instance, **kwargs):
    """
    Trackt Image-Deletion in Note
    Wird ausgeführt BEFORE Note.delete()
    """
    # Prüfe ob ein Bild existiert
    if instance.image and instance.image.name:
        try:
            # Hole Dateigröße aus ImageField
            file_size = instance.image.size if hasattr(instance.image, 'size') else 0

            if file_size > 0:
                StorageService.track_deletion(
                    user=instance.author,
                    file_size=file_size,
                    app_name='organization',
                    metadata={
                        'note_id': instance.id,
                        'note_title': instance.title,
                        'filename': os.path.basename(instance.image.name),
                    }
                )
                logger.info(
                    f"Tracked organization image deletion: {os.path.basename(instance.image.name)} "
                    f"({file_size} bytes) for user {instance.author.username}"
                )
        except Exception as e:
            logger.error(f"Failed to track organization image deletion: {str(e)}")


@receiver(pre_delete, sender=IdeaBoard)
def track_board_images_deletion(sender, instance, **kwargs):
    """
    Trackt alle Board-Bilder bei Board-Deletion
    Findet alle BoardElements vom Typ 'image' und trackt deren Speicher
    """
    try:
        # Hole alle Image-Elements des Boards
        image_elements = instance.elements.filter(element_type='image')

        for element in image_elements:
            try:
                # Extrahiere URL aus element.data
                element_data = element.data if isinstance(element.data, dict) else {}
                image_url = element_data.get('url') or element_data.get('src')

                if not image_url:
                    continue

                # Extrahiere Pfad aus URL (entferne /media/ prefix)
                # URL Format: /media/board_images/xxxxx.ext oder volle URL
                match = re.search(r'board_images/[^/\s]+', image_url)
                if not match:
                    continue

                file_path = match.group(0)

                # Hole Dateigröße vom Storage
                if default_storage.exists(file_path):
                    file_size = default_storage.size(file_path)

                    StorageService.track_deletion(
                        user=element.created_by,
                        file_size=file_size,
                        app_name='organization',
                        metadata={
                            'board_id': instance.id,
                            'board_title': instance.title,
                            'element_id': element.id,
                            'filename': os.path.basename(file_path),
                            'file_type': 'board_image',
                        }
                    )
                    logger.info(
                        f"Tracked board image deletion: {os.path.basename(file_path)} "
                        f"({file_size} bytes) from board {instance.title}"
                    )

                    # Lösche die Datei vom Storage
                    default_storage.delete(file_path)

            except Exception as e:
                logger.error(f"Failed to track individual board image: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Failed to track board images deletion: {str(e)}")


@receiver(pre_delete, sender=BoardElement)
def track_board_element_image_deletion(sender, instance, **kwargs):
    """
    Trackt Deletion eines einzelnen Board-Elements vom Typ 'image'
    """
    # Nur für Image-Elements
    if instance.element_type != 'image':
        return

    try:
        # Extrahiere URL aus element.data
        element_data = instance.data if isinstance(instance.data, dict) else {}
        image_url = element_data.get('url') or element_data.get('src')

        if not image_url:
            return

        # Extrahiere Pfad aus URL
        match = re.search(r'board_images/[^/\s]+', image_url)
        if not match:
            return

        file_path = match.group(0)

        # Hole Dateigröße vom Storage
        if default_storage.exists(file_path):
            file_size = default_storage.size(file_path)

            StorageService.track_deletion(
                user=instance.created_by,
                file_size=file_size,
                app_name='organization',
                metadata={
                    'board_id': instance.board.id,
                    'board_title': instance.board.title,
                    'element_id': instance.id,
                    'filename': os.path.basename(file_path),
                    'file_type': 'board_image',
                }
            )
            logger.info(
                f"Tracked board element image deletion: {os.path.basename(file_path)} "
                f"({file_size} bytes) from board {instance.board.title}"
            )

            # Lösche die Datei vom Storage
            default_storage.delete(file_path)

    except Exception as e:
        logger.error(f"Failed to track board element image deletion: {str(e)}")

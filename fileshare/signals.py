"""
Fileshare Storage Tracking Signals
===================================
Trackt File-Uploads und Deletions im globalen Storage-System
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TransferFile
from core.storage_service import StorageService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TransferFile)
def track_fileshare_upload(sender, instance, created, **kwargs):
    """
    Trackt File-Upload in Fileshare
    Wird ausgeführt nach TransferFile.save()
    """
    if created and instance.transfer.sender:
        # Nur tracken wenn es einen User gibt (nicht für anonyme Uploads)
        try:
            StorageService.track_upload(
                user=instance.transfer.sender,
                file_size=instance.file_size,
                app_name='fileshare',
                metadata={
                    'transfer_id': str(instance.transfer.id),
                    'filename': instance.original_filename,
                    'file_type': instance.file_type,
                }
            )
            logger.info(
                f"Tracked fileshare upload: {instance.original_filename} "
                f"({instance.file_size} bytes) for user {instance.transfer.sender.username}"
            )
        except Exception as e:
            # Bei Storage-Fehler loggen aber nicht blockieren
            # (File ist bereits hochgeladen, nur Tracking failed)
            logger.error(f"Failed to track fileshare upload: {str(e)}")


@receiver(post_delete, sender=TransferFile)
def track_fileshare_deletion(sender, instance, **kwargs):
    """
    Trackt File-Deletion in Fileshare
    Wird ausgeführt nach TransferFile.delete()
    """
    if instance.transfer.sender:
        try:
            StorageService.track_deletion(
                user=instance.transfer.sender,
                file_size=instance.file_size,
                app_name='fileshare',
                metadata={
                    'transfer_id': str(instance.transfer.id),
                    'filename': instance.original_filename,
                    'file_type': instance.file_type,
                }
            )
            logger.info(
                f"Tracked fileshare deletion: {instance.original_filename} "
                f"({instance.file_size} bytes) for user {instance.transfer.sender.username}"
            )
        except Exception as e:
            logger.error(f"Failed to track fileshare deletion: {str(e)}")

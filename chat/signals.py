"""
Chat Storage Tracking Signals
==============================
Trackt File-Uploads und Deletions im globalen Storage-System
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ChatMessageAttachment, ChatMessage
from core.storage_service import StorageService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ChatMessageAttachment)
def track_chat_attachment_upload(sender, instance, created, **kwargs):
    """
    Trackt File-Upload in Chat
    Wird ausgeführt nach ChatMessageAttachment.save()
    """
    if created and instance.message.sender:
        # Nur tracken wenn es einen User gibt (nicht für anonyme Nachrichten)
        try:
            StorageService.track_upload(
                user=instance.message.sender,
                file_size=instance.file_size,
                app_name='chat',
                metadata={
                    'attachment_id': instance.id,
                    'filename': instance.filename,
                    'file_type': instance.file_type,
                    'chat_room_id': instance.message.chat_room.id,
                    'message_id': instance.message.id,
                }
            )
            logger.info(
                f"Tracked chat attachment upload: {instance.filename} "
                f"({instance.file_size} bytes) for user {instance.message.sender.username}"
            )
        except Exception as e:
            # Bei Storage-Fehler loggen aber nicht blockieren
            # (File ist bereits hochgeladen, nur Tracking failed)
            logger.error(f"Failed to track chat attachment upload: {str(e)}")


@receiver(post_delete, sender=ChatMessageAttachment)
def track_chat_attachment_deletion(sender, instance, **kwargs):
    """
    Trackt File-Deletion in Chat
    Wird ausgeführt nach ChatMessageAttachment.delete()
    """
    if instance.message.sender:
        try:
            StorageService.track_deletion(
                user=instance.message.sender,
                file_size=instance.file_size,
                app_name='chat',
                metadata={
                    'attachment_id': instance.id,
                    'filename': instance.filename,
                    'file_type': instance.file_type,
                    'chat_room_id': instance.message.chat_room.id,
                    'message_id': instance.message.id,
                }
            )
            logger.info(
                f"Tracked chat attachment deletion: {instance.filename} "
                f"({instance.file_size} bytes) for user {instance.message.sender.username}"
            )
        except Exception as e:
            logger.error(f"Failed to track chat attachment deletion: {str(e)}")


@receiver(post_save, sender=ChatMessage)
def send_loomconnect_message_notification(sender, instance, created, **kwargs):
    """
    Send email notification for new chat messages in LoomConnect connections
    """
    if created and instance.sender:
        try:
            # Import here to avoid circular imports
            from loomconnect.signals import send_new_message_email
            send_new_message_email(instance)
        except Exception as e:
            logger.error(f"Failed to send LoomConnect message notification: {str(e)}")

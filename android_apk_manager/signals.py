"""
Android APK Manager Storage Tracking Signals
Trackt APK-Uploads im globalen Storage-System
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AppVersion
from core.storage_service import StorageService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AppVersion)
def track_apk_upload(sender, instance, created, **kwargs):
    """Trackt APK-Upload im Storage-System"""
    if created and instance.app.created_by:
        try:
            StorageService.track_upload(
                user=instance.app.created_by,
                file_size=instance.file_size,
                app_name='android_apk_manager',
                metadata={
                    'app_id': str(instance.app.id),
                    'app_name': instance.app.name,
                    'package_name': instance.app.package_name,
                    'version_name': instance.version_name,
                    'version_code': instance.version_code,
                    'channel': instance.channel,
                }
            )
            logger.info(
                f"Tracked APK upload: {instance.app.name} v{instance.version_name} "
                f"({instance.file_size} bytes) for user {instance.app.created_by.username}"
            )
        except Exception as e:
            logger.error(f"Failed to track APK upload: {str(e)}")


@receiver(post_delete, sender=AppVersion)
def track_apk_deletion(sender, instance, **kwargs):
    """Trackt APK-Deletion im Storage-System"""
    if instance.app.created_by:
        try:
            StorageService.track_deletion(
                user=instance.app.created_by,
                file_size=instance.file_size,
                app_name='android_apk_manager',
                metadata={
                    'app_id': str(instance.app.id),
                    'app_name': instance.app.name,
                    'package_name': instance.app.package_name,
                    'version_name': instance.version_name,
                    'version_code': instance.version_code,
                }
            )
            logger.info(
                f"Tracked APK deletion: {instance.app.name} v{instance.version_name} "
                f"({instance.file_size} bytes) for user {instance.app.created_by.username}"
            )
        except Exception as e:
            logger.error(f"Failed to track APK deletion: {str(e)}")

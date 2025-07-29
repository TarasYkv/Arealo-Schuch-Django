"""
Django signals for automatic UserStorage creation and management
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from .models import UserStorage, Video

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_storage(sender, instance, created, **kwargs):
    """
    Automatically create UserStorage with free 50MB plan for new users
    """
    if created:
        try:
            user_storage, storage_created = UserStorage.objects.get_or_create(
                user=instance,
                defaults={
                    'used_storage': 0,
                    'max_storage': 52428800,  # 50MB in bytes
                    'is_premium': False,
                }
            )
            
            if storage_created:
                logger.info(f"Created free 50MB storage for new user: {instance.username}")
            
        except Exception as e:
            logger.error(f"Failed to create UserStorage for user {instance.username}: {str(e)}")


@receiver(post_save, sender=User)
def ensure_user_storage_exists(sender, instance, **kwargs):
    """
    Ensure UserStorage exists for any user (safety net)
    """
    try:
        user_storage, created = UserStorage.objects.get_or_create(
            user=instance,
            defaults={
                'used_storage': 0,
                'max_storage': 52428800,  # 50MB in bytes
                'is_premium': False,
            }
        )
        
        if created:
            logger.info(f"Created missing UserStorage for existing user: {instance.username}")
            
    except Exception as e:
        logger.error(f"Failed to ensure UserStorage for user {instance.username}: {str(e)}")


@receiver(post_delete, sender=Video)
def update_storage_on_video_delete(sender, instance, **kwargs):
    """
    Update user storage when a video is deleted
    """
    try:
        user_storage = UserStorage.objects.get(user=instance.user)
        
        # Only subtract if video was active (not archived)
        if instance.status == 'active':
            user_storage.used_storage = max(0, user_storage.used_storage - instance.file_size)
            user_storage.save()
            
            logger.info(f"Updated storage for {instance.user.username} after video deletion: -{instance.file_size} bytes")
            
    except UserStorage.DoesNotExist:
        logger.warning(f"UserStorage not found for user {instance.user.username} during video deletion")
    except Exception as e:
        logger.error(f"Failed to update storage for user {instance.user.username}: {str(e)}")


@receiver(post_save, sender=Video)
def update_storage_on_video_save(sender, instance, created, **kwargs):
    """
    Update user storage when a video is created or status changes
    """
    if not created:
        return  # Only handle new videos, status changes handled elsewhere
        
    try:
        user_storage = UserStorage.objects.get(user=instance.user)
        
        # Add storage usage for new active videos
        if instance.status == 'active':
            user_storage.used_storage += instance.file_size
            user_storage.save()
            
            logger.info(f"Updated storage for {instance.user.username} after video upload: +{instance.file_size} bytes")
            
    except UserStorage.DoesNotExist:
        # Create UserStorage if it doesn't exist (safety net)
        user_storage = UserStorage.objects.create(
            user=instance.user,
            used_storage=instance.file_size if instance.status == 'active' else 0,
            max_storage=52428800,  # 50MB default
            is_premium=False,
        )
        logger.info(f"Created UserStorage for user {instance.user.username} during video upload")
        
    except Exception as e:
        logger.error(f"Failed to update storage for user {instance.user.username}: {str(e)}")


def reset_user_to_free_plan(user):
    """
    Reset user to free 50MB plan (used when subscription ends)
    """
    try:
        user_storage, created = UserStorage.objects.get_or_create(
            user=user,
            defaults={
                'used_storage': 0,
                'max_storage': 52428800,  # 50MB
                'is_premium': False,
            }
        )
        
        if not created:
            # Reset to free plan
            user_storage.max_storage = 52428800  # 50MB
            user_storage.is_premium = False
            user_storage.save()
            
        logger.info(f"Reset user {user.username} to free 50MB plan")
        
        # Check if storage overage handling is needed
        if user_storage.is_storage_exceeded():
            from .storage_management import StorageOverageService
            StorageOverageService.check_user_storage_overage(user)
            
        return user_storage
        
    except Exception as e:
        logger.error(f"Failed to reset user {user.username} to free plan: {str(e)}")
        return None
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Subscription
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Subscription)
def sync_storage_on_subscription_update(sender, instance, created, **kwargs):
    """Sync video storage when subscription is created or updated"""
    try:
        from videos.subscription_sync import StorageSubscriptionSync
        StorageSubscriptionSync.sync_user_storage(instance.customer.user)
        logger.info(f"Synced storage for user {instance.customer.user.id} after subscription update")
    except Exception as e:
        logger.error(f"Error syncing storage after subscription update: {str(e)}")


@receiver(post_delete, sender=Subscription)
def sync_storage_on_subscription_delete(sender, instance, **kwargs):
    """Sync video storage when subscription is deleted"""
    try:
        from videos.subscription_sync import StorageSubscriptionSync
        StorageSubscriptionSync.sync_user_storage(instance.customer.user)
        logger.info(f"Synced storage for user {instance.customer.user.id} after subscription deletion")
    except Exception as e:
        logger.error(f"Error syncing storage after subscription deletion: {str(e)}")
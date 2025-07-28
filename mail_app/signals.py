"""
Django signals for Mail App
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Email


@receiver(post_delete, sender=Email)
def update_folder_counts_on_delete(sender, instance, **kwargs):
    """
    Update folder counts when an email is deleted.
    """
    if instance.folder and hasattr(instance.folder, 'update_counts'):
        instance.folder.update_counts()


@receiver(post_save, sender=Email)
def update_folder_counts_on_save(sender, instance, created, **kwargs):
    """
    Update folder counts when an email is saved (e.g., read status changed).
    Only update if read status might have changed.
    """
    if not created and instance.folder and hasattr(instance.folder, 'update_counts'):
        # Update folder counts when emails are saved/updated
        instance.folder.update_counts()
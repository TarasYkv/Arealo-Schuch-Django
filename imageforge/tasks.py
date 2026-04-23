"""
Celery Tasks für ImageForge - Async Thumbnail-Generierung
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_thumbnail_async(self, image_field_name: str, model_name: str, pk: int, size: str = 'medium'):
    """
    Generiert ein Thumbnail asynchron im Hintergrund.
    
    Args:
        image_field_name: Name des ImageField (z.B. 'generated_image')
        model_name: Model-Klasse als String (z.B. 'ImageGeneration')
        pk: Primary Key des Objekts
        size: Thumbnail-Größe ('small', 'medium', 'large')
    """
    try:
        from django.apps import apps
        from core.thumbnails import generate_thumbnail
        
        # Model laden
        Model = apps.get_model('imageforge', model_name)
        obj = Model.objects.get(pk=pk)
        
        # ImageField holen
        image_field = getattr(obj, image_field_name, None)
        if not image_field:
            logger.warning(f"No image field '{image_field_name}' on {model_name} pk={pk}")
            return
        
        # Thumbnail generieren
        thumb_url = generate_thumbnail(image_field, size)
        logger.info(f"Thumbnail generated for {model_name} pk={pk}: {thumb_url}")
        
        return thumb_url
        
    except Exception as e:
        logger.error(f"Error generating thumbnail for {model_name} pk={pk}: {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task
def generate_all_thumbnails_for_generation(pk: int):
    """
    Generiert alle Thumbnail-Größen für eine ImageGeneration.
    """
    for size in ['small', 'medium', 'large']:
        generate_thumbnail_async.delay('generated_image', 'ImageGeneration', pk, size)

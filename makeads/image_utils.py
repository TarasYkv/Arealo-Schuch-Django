"""
Image utilities for MakeAds - Download and store DALL-E images locally
"""
import os
import requests
import uuid
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def download_and_store_dalle_image(image_url: str, creative_id: str) -> str:
    """
    Download DALL-E image from URL and store it locally
    
    Args:
        image_url: The DALL-E image URL
        creative_id: The Creative model ID for filename
    
    Returns:
        Local file path relative to MEDIA_ROOT
    """
    try:
        # Download the image
        logger.info(f"Downloading DALL-E image: {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Generate filename
        filename = f"makeads/creatives/{creative_id}_dalle.png"
        
        # Create ContentFile from downloaded data
        image_content = ContentFile(response.content)
        
        # Save to storage
        saved_path = default_storage.save(filename, image_content)
        
        logger.info(f"DALL-E image saved locally: {saved_path}")
        return saved_path
        
    except requests.RequestException as e:
        logger.error(f"Failed to download DALL-E image {image_url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error saving DALL-E image: {str(e)}")
        return None


def ensure_creative_has_local_image(creative):
    """
    Ensure a Creative has a local image file. If it only has image_url,
    download and store it locally.
    
    Args:
        creative: Creative model instance
    
    Returns:
        Boolean indicating success
    """
    # If already has local file, we're good
    if creative.image_file:
        logger.info(f"Creative {creative.id} already has local image file")
        return True
    
    # If has URL but no local file, download it
    if creative.image_url:
        logger.info(f"Downloading image for Creative {creative.id} from URL")
        local_path = download_and_store_dalle_image(creative.image_url, str(creative.id))
        
        if local_path:
            # Update the creative with local file path
            creative.image_file.name = local_path
            creative.save(update_fields=['image_file'])
            logger.info(f"Successfully stored local image for Creative {creative.id}")
            return True
        else:
            logger.warning(f"Failed to download image for Creative {creative.id}")
            return False
    
    logger.warning(f"Creative {creative.id} has no image URL or file")
    return False


def get_creative_image_url(creative):
    """
    Get the best available image URL for a Creative.
    Prioritizes local file over external URL.
    
    Args:
        creative: Creative model instance
        
    Returns:
        Image URL string or None
    """
    # First try local file
    if creative.image_file:
        return creative.image_file.url
    
    # Then try to ensure we have a local copy
    if creative.image_url:
        if ensure_creative_has_local_image(creative):
            return creative.image_file.url
        else:
            # Fallback to original URL (might be expired)
            return creative.image_url
    
    return None


def batch_migrate_dalle_images():
    """
    Migrate all existing Creatives with image_url but no image_file
    to have local copies.
    """
    from django.db import models
    from .models import Creative
    
    creatives_to_migrate = Creative.objects.filter(
        image_url__isnull=False
    ).exclude(image_url='').filter(
        models.Q(image_file__isnull=True) | models.Q(image_file='')
    )
    
    logger.info(f"Found {creatives_to_migrate.count()} creatives to migrate")
    
    success_count = 0
    fail_count = 0
    
    for creative in creatives_to_migrate:
        try:
            if ensure_creative_has_local_image(creative):
                success_count += 1
                logger.info(f"✅ Migrated Creative {creative.id}: {creative.title}")
            else:
                fail_count += 1
                logger.warning(f"❌ Failed to migrate Creative {creative.id}: {creative.title}")
        except Exception as e:
            fail_count += 1
            logger.error(f"❌ Error migrating Creative {creative.id}: {str(e)}")
    
    logger.info(f"Migration complete: {success_count} successful, {fail_count} failed")
    return success_count, fail_count
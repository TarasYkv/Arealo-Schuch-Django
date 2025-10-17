"""
Streamrec Storage Helpers
==========================
Helper functions für Storage-Tracking in Streamrec
Da Streamrec Dateien direkt speichert (ohne Model), kein Signal-basiertes Tracking möglich
"""

from core.storage_service import StorageService, StorageQuotaExceeded
import logging

logger = logging.getLogger(__name__)


def track_recording_upload(user, file_size_bytes, filename, recording_type='audio'):
    """
    Trackt Recording-Upload im globalen Storage-System

    Args:
        user: User object
        file_size_bytes: Größe in Bytes
        filename: Dateiname
        recording_type: 'audio' oder 'video'

    Raises:
        StorageQuotaExceeded: Wenn Quota überschritten wird
    """
    try:
        StorageService.track_upload(
            user=user,
            file_size=file_size_bytes,
            app_name='streamrec',
            metadata={
                'filename': filename,
                'recording_type': recording_type,
            }
        )
        logger.info(
            f"Tracked streamrec {recording_type} upload: {filename} "
            f"({file_size_bytes} bytes) for user {user.username}"
        )
    except StorageQuotaExceeded as e:
        logger.warning(f"Storage quota exceeded for {user.username}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to track streamrec upload: {str(e)}")
        # Bei anderen Fehlern nicht blockieren
        pass


def track_recording_deletion(user, file_size_bytes, filename, recording_type='audio'):
    """
    Trackt Recording-Deletion im globalen Storage-System

    Args:
        user: User object
        file_size_bytes: Größe in Bytes
        filename: Dateiname
        recording_type: 'audio' oder 'video'
    """
    try:
        StorageService.track_deletion(
            user=user,
            file_size=file_size_bytes,
            app_name='streamrec',
            metadata={
                'filename': filename,
                'recording_type': recording_type,
            }
        )
        logger.info(
            f"Tracked streamrec {recording_type} deletion: {filename} "
            f"({file_size_bytes} bytes) for user {user.username}"
        )
    except Exception as e:
        logger.error(f"Failed to track streamrec deletion: {str(e)}")


def check_storage_quota(user, file_size_bytes):
    """
    Prüft ob User genug Speicherplatz für Upload hat

    Args:
        user: User object
        file_size_bytes: Benötigte Größe in Bytes

    Returns:
        tuple: (has_space: bool, available_bytes: int, error_message: str or None)
    """
    has_space, available = StorageService.check_quota(user, file_size_bytes)

    if not has_space:
        return (
            False,
            available,
            f"Speicherlimit überschritten. Verfügbar: {available / (1024*1024):.2f}MB, "
            f"Benötigt: {file_size_bytes / (1024*1024):.2f}MB"
        )

    return True, available, None

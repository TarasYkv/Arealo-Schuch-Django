"""
Global Storage Service
======================
Zentraler Service für Speicherverwaltung über alle Apps hinweg.
Verwendet von: Videos, Fileshare, Streamrec
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class StorageQuotaExceeded(Exception):
    """Exception wenn Speicherlimit überschritten wird"""
    def __init__(self, user, required_size, available_size):
        self.user = user
        self.required_size = required_size
        self.available_size = available_size
        super().__init__(
            f"Speicherlimit überschritten für {user.username}. "
            f"Benötigt: {required_size / (1024*1024):.2f}MB, "
            f"Verfügbar: {available_size / (1024*1024):.2f}MB"
        )


class StorageService:
    """Zentraler Service für Speicherverwaltung"""

    # Storage Tiers mit Preisen (in MB)
    STORAGE_TIERS = {
        100: {'monthly': Decimal('0.00'), 'yearly': Decimal('0.00'), 'name': 'Kostenlos (100MB)'},
        1024: {'monthly': Decimal('2.99'), 'yearly': Decimal('29.90'), 'name': '1GB Plan'},
        3072: {'monthly': Decimal('4.99'), 'yearly': Decimal('49.90'), 'name': '3GB Plan'},
        5120: {'monthly': Decimal('7.99'), 'yearly': Decimal('79.90'), 'name': '5GB Plan'},
        10240: {'monthly': Decimal('9.99'), 'yearly': Decimal('99.90'), 'name': '10GB Plan'},
    }

    @classmethod
    def get_or_create_user_storage(cls, user):
        """Holt oder erstellt UserStorage für einen User"""
        from videos.models import UserStorage

        storage, created = UserStorage.objects.get_or_create(
            user=user,
            defaults={
                'used_storage': 0,
                'max_storage': 100 * 1024 * 1024,  # 100MB in Bytes
                'is_premium': False
            }
        )

        if created:
            logger.info(f"Created UserStorage for {user.username} with 100MB free tier")

        return storage

    @classmethod
    def check_quota(cls, user, file_size):
        """
        Prüft ob User genug Speicherplatz hat

        Args:
            user: User object
            file_size: Größe in Bytes

        Returns:
            tuple: (has_space: bool, available_bytes: int)
        """
        storage = cls.get_or_create_user_storage(user)
        available = storage.max_storage - storage.used_storage
        has_space = file_size <= available

        return has_space, available

    @classmethod
    @transaction.atomic
    def track_upload(cls, user, file_size, app_name, metadata=None):
        """
        Trackt einen File-Upload und aktualisiert Speicherverbrauch

        Args:
            user: User object
            file_size: Größe in Bytes
            app_name: Name der App (z.B. 'videos', 'fileshare', 'streamrec')
            metadata: Optional dict mit zusätzlichen Infos

        Raises:
            StorageQuotaExceeded: Wenn Quota überschritten wird
        """
        storage = cls.get_or_create_user_storage(user)

        # Quota prüfen
        has_space, available = cls.check_quota(user, file_size)
        if not has_space:
            raise StorageQuotaExceeded(user, file_size, available)

        # Speicher aktualisieren
        storage.used_storage += file_size
        storage.save(update_fields=['used_storage', 'updated_at'])

        # Log erstellen
        from core.models import StorageLog
        StorageLog.objects.create(
            user=user,
            app_name=app_name,
            action='upload',
            size_bytes=file_size,
            metadata=metadata or {}
        )

        logger.info(
            f"Tracked upload for {user.username}: {file_size / (1024*1024):.2f}MB "
            f"in {app_name}. Total: {storage.used_storage / (1024*1024):.2f}MB / "
            f"{storage.max_storage / (1024*1024):.2f}MB"
        )

        # Check if notification should be sent after upload
        cls._check_and_send_notification(user, storage)

        return storage

    @classmethod
    @transaction.atomic
    def track_deletion(cls, user, file_size, app_name, metadata=None):
        """
        Trackt eine File-Löschung und gibt Speicher frei

        Args:
            user: User object
            file_size: Größe in Bytes
            app_name: Name der App
            metadata: Optional dict mit zusätzlichen Infos
        """
        storage = cls.get_or_create_user_storage(user)

        # Speicher freigeben
        storage.used_storage = max(0, storage.used_storage - file_size)
        storage.save(update_fields=['used_storage', 'updated_at'])

        # Log erstellen
        from core.models import StorageLog
        StorageLog.objects.create(
            user=user,
            app_name=app_name,
            action='delete',
            size_bytes=file_size,
            metadata=metadata or {}
        )

        logger.info(
            f"Tracked deletion for {user.username}: {file_size / (1024*1024):.2f}MB "
            f"from {app_name}. Total: {storage.used_storage / (1024*1024):.2f}MB"
        )

        return storage

    @classmethod
    def get_usage_stats(cls, user):
        """
        Gibt detaillierte Speichernutzungs-Statistiken zurück

        Returns:
            dict mit:
                - used_mb: Verwendeter Speicher in MB
                - max_mb: Maximum in MB
                - used_gb: Verwendet in GB
                - max_gb: Maximum in GB
                - percentage: Prozentuale Nutzung
                - available_bytes: Verfügbare Bytes
                - is_exceeded: Bool ob Limit überschritten
                - by_app: Dict mit Nutzung pro App
        """
        from core.models import StorageLog
        from django.db.models import Sum

        storage = cls.get_or_create_user_storage(user)

        # Nutzung pro App
        app_usage = StorageLog.objects.filter(
            user=user
        ).values('app_name').annotate(
            total=Sum('size_bytes')
        )

        by_app = {item['app_name']: item['total'] for item in app_usage}

        used_mb = storage.used_storage / (1024 * 1024)
        max_mb = storage.max_storage / (1024 * 1024)
        percentage = (storage.used_storage / storage.max_storage * 100) if storage.max_storage > 0 else 0

        return {
            'used_bytes': storage.used_storage,
            'max_bytes': storage.max_storage,
            'used_mb': used_mb,
            'max_mb': max_mb,
            'used_gb': used_mb / 1024,
            'max_gb': max_mb / 1024,
            'percentage': round(percentage, 2),
            'available_bytes': storage.max_storage - storage.used_storage,
            'is_exceeded': storage.used_storage > storage.max_storage,
            'by_app': by_app,
            'tier_name': storage.get_tier_name(),
            'current_price': float(storage.get_current_price()),
        }

    @classmethod
    def get_tier_info(cls, storage_mb):
        """
        Gibt Info zu einem Storage-Tier zurück

        Args:
            storage_mb: Speicher in MB

        Returns:
            dict mit tier info oder None
        """
        tier = cls.STORAGE_TIERS.get(storage_mb)
        if tier:
            return {
                'mb': storage_mb,
                'gb': storage_mb / 1024 if storage_mb >= 1024 else None,
                'name': tier['name'],
                'price_monthly': float(tier['monthly']),
                'price_yearly': float(tier['yearly']),
                'bytes': storage_mb * 1024 * 1024,
            }
        return None

    @classmethod
    def get_all_tiers(cls):
        """Gibt alle verfügbaren Storage-Tiers zurück"""
        return [
            {
                'mb': tier_mb,
                'gb': tier_mb / 1024 if tier_mb >= 1024 else None,
                'name': data['name'],
                'price_monthly': float(data['monthly']),
                'price_yearly': float(data['yearly']),
                'bytes': tier_mb * 1024 * 1024,
                'is_free': data['monthly'] == 0,
            }
            for tier_mb, data in sorted(cls.STORAGE_TIERS.items())
        ]

    @classmethod
    def upgrade_user_storage(cls, user, new_storage_mb):
        """
        Upgraded User-Speicher auf neues Tier

        Hinweis: Kostenpflichtige Pläne erhalten automatisch +100MB Basis-Speicher
        - Kostenlos: 100MB
        - 1GB Plan: 1024MB + 100MB = 1124MB
        - 3GB Plan: 3072MB + 100MB = 3172MB
        - etc.

        Args:
            user: User object
            new_storage_mb: Neues Limit in MB (ohne Basis-Speicher)

        Returns:
            UserStorage object
        """
        storage = cls.get_or_create_user_storage(user)

        # Kostenpflichtige Pläne erhalten +100MB Basis-Speicher
        if new_storage_mb > 100:
            actual_storage_mb = new_storage_mb + 100
        else:
            actual_storage_mb = new_storage_mb

        new_bytes = actual_storage_mb * 1024 * 1024
        old_mb = storage.max_storage / (1024 * 1024)

        storage.max_storage = new_bytes
        storage.is_premium = new_storage_mb > 100
        storage.save(update_fields=['max_storage', 'is_premium', 'updated_at'])

        logger.info(
            f"Upgraded storage for {user.username}: {old_mb}MB → {actual_storage_mb}MB "
            f"(Plan: {new_storage_mb}MB + 100MB Basis)"
        )

        return storage

    @classmethod
    def check_downgrade_feasibility(cls, user, new_storage_mb):
        """
        Prüft ob ein Downgrade möglich ist (verwendet < neues Limit)

        Returns:
            dict: {
                'feasible': bool,
                'current_usage_mb': float,
                'new_limit_mb': int,
                'overage_mb': float (wenn nicht feasible)
            }
        """
        storage = cls.get_or_create_user_storage(user)
        current_usage_mb = storage.used_storage / (1024 * 1024)
        overage_mb = max(0, current_usage_mb - new_storage_mb)

        return {
            'feasible': current_usage_mb <= new_storage_mb,
            'current_usage_mb': round(current_usage_mb, 2),
            'new_limit_mb': new_storage_mb,
            'overage_mb': round(overage_mb, 2) if overage_mb > 0 else 0,
        }

    @classmethod
    def _check_and_send_notification(cls, user, storage):
        """
        Prüft ob Benachrichtigung nach Upload gesendet werden soll

        Args:
            user: User object
            storage: UserStorage object
        """
        try:
            from core.storage_notifications import StorageNotificationService

            # Berechne Quota-Prozentsatz
            usage_percent = (storage.used_storage / storage.max_storage * 100) if storage.max_storage > 0 else 0

            # Bestimme Warnstufe
            warning_level = None
            if usage_percent >= 100:
                warning_level = 'quota_exceeded'
            elif usage_percent >= 90:
                warning_level = 'warning_90'
            elif usage_percent >= 75:
                warning_level = 'warning_75'

            # Sende Benachrichtigung falls nötig
            if warning_level and StorageNotificationService._should_send_notification(storage, warning_level):
                StorageNotificationService.send_quota_warning(user, usage_percent, warning_level)
                logger.info(f"Sent storage notification ({warning_level}) to {user.username}")

        except Exception as e:
            # Fehler bei Benachrichtigung sollen Upload nicht blockieren
            logger.error(f"Failed to send storage notification: {str(e)}")

    @classmethod
    def recalculate_storage(cls, user):
        """
        Berechnet den tatsächlichen Speicherverbrauch aus allen Apps neu
        und aktualisiert UserStorage.

        Returns:
            dict mit Details zur Berechnung
        """
        import os
        from django.core.files.storage import default_storage

        storage = cls.get_or_create_user_storage(user)
        old_used = storage.used_storage
        total_bytes = 0
        by_app = {}

        # Videos
        try:
            from videos.models import Video
            videos = Video.objects.filter(user=user, video_file__isnull=False)
            video_total = 0
            for video in videos:
                if video.video_file and hasattr(video.video_file, 'size'):
                    try:
                        video_total += video.video_file.size
                    except Exception:
                        pass
            by_app['videos'] = video_total
            total_bytes += video_total
        except Exception as e:
            logger.error(f"Error calculating videos storage: {e}")

        # Fileshare
        try:
            from fileshare.models import TransferFile
            fileshare_files = TransferFile.objects.filter(
                transfer__sender=user,
                file__isnull=False
            )
            fileshare_total = 0
            for fs_file in fileshare_files:
                if fs_file.file and hasattr(fs_file.file, 'size'):
                    try:
                        fileshare_total += fs_file.file.size
                    except Exception:
                        pass
            by_app['fileshare'] = fileshare_total
            total_bytes += fileshare_total
        except Exception as e:
            logger.error(f"Error calculating fileshare storage: {e}")

        # Organization - Notes with images
        try:
            from organization.models import Note, BoardElement
            notes = Note.objects.filter(author=user, image__isnull=False)
            org_total = 0
            for note in notes:
                if note.image and hasattr(note.image, 'size'):
                    try:
                        org_total += note.image.size
                    except Exception:
                        pass

            # Board images
            board_elements = BoardElement.objects.filter(
                created_by=user,
                element_type='image'
            )
            import re
            for element in board_elements:
                try:
                    element_data = element.data if isinstance(element.data, dict) else {}
                    image_url = element_data.get('url') or element_data.get('src')
                    if not image_url:
                        continue
                    match = re.search(r'board_images/[^/\s]+', image_url)
                    if match and default_storage.exists(match.group(0)):
                        org_total += default_storage.size(match.group(0))
                except Exception:
                    pass

            by_app['organization'] = org_total
            total_bytes += org_total
        except Exception as e:
            logger.error(f"Error calculating organization storage: {e}")

        # Chat attachments
        try:
            from chat.models import ChatMessageAttachment
            attachments = ChatMessageAttachment.objects.filter(
                message__sender=user,
                file__isnull=False
            )
            chat_total = 0
            for attachment in attachments:
                if attachment.file and hasattr(attachment.file, 'size'):
                    try:
                        chat_total += attachment.file.size
                    except Exception:
                        pass
            by_app['chat'] = chat_total
            total_bytes += chat_total
        except Exception as e:
            logger.error(f"Error calculating chat storage: {e}")

        # Streamrec
        try:
            from django.conf import settings
            user_prefix = f"{user.id}_"
            streamrec_total = 0
            recording_types = ['audio_recordings', 'video_recordings']

            for dir_name in recording_types:
                media_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
                if os.path.exists(media_dir):
                    for filename in os.listdir(media_dir):
                        if filename.startswith(user_prefix):
                            filepath = os.path.join(media_dir, filename)
                            if os.path.isfile(filepath):
                                streamrec_total += os.path.getsize(filepath)

            by_app['streamrec'] = streamrec_total
            total_bytes += streamrec_total
        except Exception as e:
            logger.error(f"Error calculating streamrec storage: {e}")

        # Ideopin (PinProject + Pin Bilder)
        try:
            from ideopin.models import PinProject, Pin
            ideopin_total = 0

            # PinProject Bilder (product_image, generated_image, final_image)
            pin_projects = PinProject.objects.filter(user=user)
            for project in pin_projects:
                for field_name in ['product_image', 'generated_image', 'final_image']:
                    field = getattr(project, field_name, None)
                    if field and hasattr(field, 'size'):
                        try:
                            ideopin_total += field.size
                        except Exception:
                            pass

            # Pin Bilder (Multi-Pin Feature: generated_image, final_image)
            pins = Pin.objects.filter(project__user=user)
            for pin in pins:
                for field_name in ['generated_image', 'final_image']:
                    field = getattr(pin, field_name, None)
                    if field and hasattr(field, 'size'):
                        try:
                            ideopin_total += field.size
                        except Exception:
                            pass

            by_app['ideopin'] = ideopin_total
            total_bytes += ideopin_total
        except Exception as e:
            logger.error(f"Error calculating ideopin storage: {e}")

        # UserStorage aktualisieren
        storage.used_storage = total_bytes
        storage.save(update_fields=['used_storage', 'updated_at'])

        logger.info(
            f"Recalculated storage for {user.username}: "
            f"{old_used / (1024*1024):.2f}MB → {total_bytes / (1024*1024):.2f}MB"
        )

        return {
            'old_bytes': old_used,
            'new_bytes': total_bytes,
            'old_mb': old_used / (1024 * 1024),
            'new_mb': total_bytes / (1024 * 1024),
            'difference_bytes': total_bytes - old_used,
            'difference_mb': (total_bytes - old_used) / (1024 * 1024),
            'by_app': by_app,
        }

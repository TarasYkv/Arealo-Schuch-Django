"""
Storage Quota Notification System
==================================
Sendet E-Mail-Benachrichtigungen bei Speicher-Quota-Überschreitung
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import get_user_model
from videos.models import UserStorage
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class StorageNotificationService:
    """Service für Storage-Quota Benachrichtigungen"""

    # Warnstufen (Prozent der Quota)
    WARNING_LEVELS = {
        75: 'warning_75',
        90: 'warning_90',
        100: 'quota_exceeded',
    }

    @classmethod
    def check_and_notify_all_users(cls):
        """
        Prüft alle User und sendet Benachrichtigungen bei Bedarf
        Sollte via Cron täglich laufen
        """
        users_notified = []
        total_checked = 0

        for storage in UserStorage.objects.select_related('user').all():
            total_checked += 1

            # Prüfe Quota-Level
            usage_percent = (storage.used_storage / storage.max_storage * 100) if storage.max_storage > 0 else 0

            # Bestimme Warnstufe
            warning_level = None
            for threshold in sorted(cls.WARNING_LEVELS.keys(), reverse=True):
                if usage_percent >= threshold:
                    warning_level = cls.WARNING_LEVELS[threshold]
                    break

            if warning_level:
                # Prüfe ob bereits benachrichtigt (nicht öfter als alle 7 Tage)
                if cls._should_send_notification(storage, warning_level):
                    try:
                        cls.send_quota_warning(storage.user, usage_percent, warning_level)
                        users_notified.append(storage.user.username)
                        logger.info(f"Sent {warning_level} notification to {storage.user.username}")
                    except Exception as e:
                        logger.error(f"Failed to send notification to {storage.user.username}: {str(e)}")

        return {
            'total_checked': total_checked,
            'users_notified': len(users_notified),
            'usernames': users_notified,
        }

    @classmethod
    def _should_send_notification(cls, storage, warning_level):
        """
        Prüft ob Benachrichtigung gesendet werden soll
        Verhindert Spam durch zu häufige Mails
        """
        from datetime import timedelta

        # Wenn noch nie benachrichtigt, sende
        if not storage.last_overage_notification:
            return True

        # Wenn letzte Benachrichtigung älter als 7 Tage, sende erneut
        days_since_last = (timezone.now() - storage.last_overage_notification).days
        if days_since_last >= 7:
            return True

        return False

    @classmethod
    def send_quota_warning(cls, user, usage_percent, warning_level):
        """
        Sendet Quota-Warnung an User

        Args:
            user: User object
            usage_percent: Prozentuale Nutzung
            warning_level: 'warning_75', 'warning_90', 'quota_exceeded'
        """
        from core.storage_service import StorageService

        # Hole Storage-Stats
        stats = StorageService.get_usage_stats(user)

        # Subject basierend auf Warning-Level
        subjects = {
            'warning_75': f'⚠️ Ihr Speicher ist zu 75% belegt',
            'warning_90': f'🚨 Ihr Speicher ist zu 90% belegt!',
            'quota_exceeded': f'❌ Speicherlimit erreicht - Upgrade erforderlich',
        }

        subject = subjects.get(warning_level, 'Speicher-Benachrichtigung')

        # E-Mail Context
        context = {
            'user': user,
            'usage_percent': round(usage_percent, 1),
            'used_mb': stats['used_mb'],
            'max_mb': stats['max_mb'],
            'used_gb': stats['used_gb'],
            'max_gb': stats['max_gb'],
            'by_app': stats['by_app'],
            'warning_level': warning_level,
            'is_critical': warning_level == 'quota_exceeded',
            'tier_name': stats['tier_name'],
            'current_price': stats['current_price'],
            'upgrade_url': 'https://yourdomain.com/payments/plans/',  # TODO: Dynamisch machen
        }

        # Rendere E-Mail Templates
        html_message = render_to_string('core/emails/storage_quota_warning.html', context)
        plain_message = render_to_string('core/emails/storage_quota_warning.txt', context)

        # Sende E-Mail
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,  # Verwendet DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        # Update last notification timestamp
        from videos.models import UserStorage
        storage = UserStorage.objects.get(user=user)
        storage.last_overage_notification = timezone.now()
        storage.storage_overage_notified = True
        storage.save(update_fields=['last_overage_notification', 'storage_overage_notified'])

        logger.info(f"Sent {warning_level} email to {user.email}")

    @classmethod
    def send_upgrade_confirmation(cls, user, old_storage_mb, new_storage_mb):
        """
        Sendet Bestätigung nach Abo-Upgrade

        Args:
            user: User object
            old_storage_mb: Altes Limit in MB
            new_storage_mb: Neues Limit in MB
        """
        subject = '✅ Speicher erfolgreich erweitert!'

        context = {
            'user': user,
            'old_storage_mb': old_storage_mb,
            'new_storage_mb': new_storage_mb,
            'old_storage_gb': round(old_storage_mb / 1024, 2),
            'new_storage_gb': round(new_storage_mb / 1024, 2),
            'dashboard_url': 'https://yourdomain.com/payments/plans/',  # TODO: Dynamisch
        }

        html_message = render_to_string('core/emails/storage_upgrade_confirmation.html', context)
        plain_message = render_to_string('core/emails/storage_upgrade_confirmation.txt', context)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Sent upgrade confirmation to {user.email}")

    @classmethod
    def send_downgrade_warning(cls, user, current_usage_mb, new_limit_mb, overage_mb):
        """
        Sendet Warnung bei Downgrade wenn aktueller Verbrauch > neues Limit

        Args:
            user: User object
            current_usage_mb: Aktueller Verbrauch in MB
            new_limit_mb: Neues Limit in MB
            overage_mb: Überschreitung in MB
        """
        subject = '⚠️ Achtung: Downgrade nicht möglich - Speicher überschritten'

        context = {
            'user': user,
            'current_usage_mb': round(current_usage_mb, 2),
            'new_limit_mb': new_limit_mb,
            'overage_mb': round(overage_mb, 2),
            'manage_url': 'https://yourdomain.com/videos/',  # TODO: Dynamisch
        }

        html_message = render_to_string('core/emails/storage_downgrade_warning.html', context)
        plain_message = render_to_string('core/emails/storage_downgrade_warning.txt', context)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Sent downgrade warning to {user.email}")

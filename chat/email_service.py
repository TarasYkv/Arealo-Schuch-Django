import logging
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from .models import ChatMessage, ChatMessageRead, ChatEmailNotificationTracker
from email_templates.services import EmailTemplateService
from email_templates.models import EmailTemplate

logger = logging.getLogger(__name__)


class ChatEmailNotificationService:
    """Service for handling chat email notifications"""

    @staticmethod
    def schedule_notification_for_message(message: ChatMessage):
        """
        Schedule email notifications for unread messages after 5 minutes
        """
        if not message.chat_room or not message.sender:
            return

        # Get all participants except the sender
        participants = message.chat_room.participants.exclude(id=message.sender.id)

        for participant in participants:
            # Skip if user has email notifications disabled
            if not getattr(participant, 'enable_chat_email_notifications', True):
                continue

            # Check if message is already read by this user
            if ChatMessageRead.objects.filter(message=message, user=participant).exists():
                continue

            # Schedule notification for 5 minutes from now
            scheduled_time = timezone.now() + timedelta(minutes=5)

            # Create or update tracker
            tracker, created = ChatEmailNotificationTracker.objects.get_or_create(
                user=participant,
                message=message,
                defaults={
                    'scheduled_send_at': scheduled_time,
                    'notification_sent': False,
                    'is_cancelled': False
                }
            )

            if created:
                logger.info(f"Scheduled email notification for {participant.username} "
                           f"for message {message.id} at {scheduled_time}")

    @staticmethod
    def cancel_notifications_for_user_in_room(user, chat_room):
        """
        Cancel pending notifications when user reads messages
        """
        # Get all unread messages in this room
        unread_messages = chat_room.messages.exclude(
            read_by__user=user
        ).exclude(sender=user)

        # Cancel notifications for these messages
        cancelled_count = ChatEmailNotificationTracker.objects.filter(
            user=user,
            message__in=unread_messages,
            notification_sent=False,
            is_cancelled=False
        ).update(
            is_cancelled=True,
            cancelled_reason='message_read'
        )

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} pending email notifications "
                       f"for {user.username} in room {chat_room.id}")

    @staticmethod
    def send_pending_notifications():
        """
        Send all pending notifications that are due
        Called by management command or celery task
        """
        now = timezone.now()

        # Get all pending notifications that are due
        pending_notifications = ChatEmailNotificationTracker.objects.filter(
            scheduled_send_at__lte=now,
            notification_sent=False,
            is_cancelled=False
        ).select_related('user', 'message', 'message__sender', 'message__chat_room')

        sent_count = 0
        for tracker in pending_notifications:
            if ChatEmailNotificationService._send_notification(tracker):
                sent_count += 1

        if sent_count > 0:
            logger.info(f"Sent {sent_count} chat email notifications")

        return sent_count

    @staticmethod
    def _send_notification(tracker: ChatEmailNotificationTracker) -> bool:
        """
        Send individual email notification
        """
        try:
            user = tracker.user
            message = tracker.message
            chat_room = message.chat_room

            # Double-check if message is still unread
            if ChatMessageRead.objects.filter(message=message, user=user).exists():
                tracker.is_cancelled = True
                tracker.cancelled_reason = 'message_read_before_send'
                tracker.save(update_fields=['is_cancelled', 'cancelled_reason'])
                return False

            # Check if user still has notifications enabled
            if not getattr(user, 'enable_chat_email_notifications', True):
                tracker.is_cancelled = True
                tracker.cancelled_reason = 'notifications_disabled'
                tracker.save(update_fields=['is_cancelled', 'cancelled_reason'])
                return False

            # Get email template
            template = EmailTemplate.objects.filter(
                template_type='chat_notification',
                is_active=True,
                is_default=True
            ).first()

            if not template:
                logger.error("No active chat notification template found")
                return False

            # Count total unread messages for this user in this room
            unread_count = chat_room.get_unread_count(user)

            # Prepare context
            domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
            site_name = getattr(settings, 'SITE_NAME', 'WorkLoom')

            context_data = {
                'recipient_name': user.get_full_name() or user.username,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'message_preview': ChatEmailNotificationService._get_message_preview(message),
                'unread_count': unread_count,
                'chat_url': f"https://{domain}{reverse('chat:home')}?room={chat_room.id}",
                'profile_url': f"https://{domain}{reverse('accounts:profile')}",
                'site_name': site_name,
            }

            # Send email using template service
            result = EmailTemplateService.send_template_email(
                template=template,
                connection=None,  # Uses SuperConfig
                recipient_email=user.email,
                recipient_name=user.get_full_name() or user.username,
                context_data=context_data
            )

            if result.get('success'):
                # Mark as sent
                tracker.notification_sent = True
                tracker.sent_at = timezone.now()
                tracker.save(update_fields=['notification_sent', 'sent_at'])

                logger.info(f"Chat email notification sent to {user.email} "
                           f"for message {message.id}")
                return True
            else:
                logger.error(f"Failed to send chat notification to {user.email}: "
                           f"{result.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error sending chat notification to {tracker.user.email}: {e}")
            return False

    @staticmethod
    def _get_message_preview(message: ChatMessage, max_length: int = 100) -> str:
        """
        Get a preview of the message content
        """
        if not message.content:
            if message.attachments.exists():
                attachment_count = message.attachments.count()
                if attachment_count == 1:
                    return "📎 Hat eine Datei gesendet"
                else:
                    return f"📎 Hat {attachment_count} Dateien gesendet"
            return "Eine neue Nachricht wurde gesendet"

        # Clean and truncate content
        preview = message.content.strip()
        if len(preview) > max_length:
            preview = preview[:max_length-3] + "..."

        return preview

    @staticmethod
    def cleanup_old_trackers(days_old: int = 7):
        """
        Cleanup old notification trackers to keep database clean
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)

        deleted_count = ChatEmailNotificationTracker.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old chat email notification trackers")

        return deleted_count
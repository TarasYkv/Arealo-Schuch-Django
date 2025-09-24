
from django.core.management.base import BaseCommand
from django.utils import timezone
from loomline.models import ScheduledNotification
from chat.utils import send_system_message

class Command(BaseCommand):
    help = 'Checks for due scheduled notifications and sends them via chat.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Get all notifications that are due and not yet sent
        notifications_to_send = ScheduledNotification.objects.filter(
            send_at__lte=now,
            sent=False
        )

        if not notifications_to_send.exists():
            self.stdout.write(self.style.SUCCESS('No pending notifications to send.'))
            return

        self.stdout.write(f'Found {notifications_to_send.count()} notifications to send...')

        for notification in notifications_to_send:
            self.stdout.write(f'Processing notification {notification.id} for user {notification.user_to_notify.username}...')
            
            # Use the chat utility function to send the message
            success, message = send_system_message(
                user_id=notification.user_to_notify.id,
                message_content=notification.message
            )

            if success:
                # Mark as sent to prevent duplicates
                notification.sent = True
                notification.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully sent notification {notification.id} and marked as sent.'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'Failed to send notification {notification.id}. Reason: {message}'
                ))

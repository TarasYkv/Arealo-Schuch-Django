from django.core.management.base import BaseCommand
from django.utils import timezone
from chat.email_service import ChatEmailNotificationService


class Command(BaseCommand):
    help = 'Send pending chat email notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=7,
            help='Cleanup notification trackers older than X days (default: 7)',
        )

    def handle(self, *args, **options):
        start_time = timezone.now()

        self.stdout.write("🚀 Starting chat email notification service...")

        # Send pending notifications
        sent_count = ChatEmailNotificationService.send_pending_notifications()

        if sent_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Sent {sent_count} email notifications")
            )
        else:
            self.stdout.write("ℹ️  No pending notifications to send")

        # Cleanup old trackers
        cleanup_days = options['cleanup_days']
        if cleanup_days > 0:
            deleted_count = ChatEmailNotificationService.cleanup_old_trackers(cleanup_days)
            if deleted_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"🧹 Cleaned up {deleted_count} old notification trackers")
                )

        elapsed = timezone.now() - start_time
        self.stdout.write(
            f"⏱️  Completed in {elapsed.total_seconds():.2f} seconds"
        )
from django.core.management.base import BaseCommand
from videos.subscription_sync import StorageSubscriptionSync


class Command(BaseCommand):
    help = 'Sync all users storage limits with their Stripe subscriptions'

    def handle(self, *args, **options):
        self.stdout.write('Starting storage subscription sync...')
        
        updated_count = StorageSubscriptionSync.sync_all_users()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully synced storage for {updated_count} users')
        )
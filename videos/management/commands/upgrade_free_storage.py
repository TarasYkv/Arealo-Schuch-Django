"""
Management command to upgrade all free users from 50MB to 100MB
Run once: python manage.py upgrade_free_storage
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from videos.models import UserStorage

User = get_user_model()


class Command(BaseCommand):
    help = 'Upgrade all free users from 50MB to 100MB storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - No changes will be made')
            )

        self.stdout.write(
            self.style.SUCCESS('🚀 Upgrading free users from 50MB to 100MB...')
        )

        # Find all users with old 50MB limit (52428800 bytes)
        old_storage_limit = 52428800  # 50MB
        new_storage_limit = 104857600  # 100MB

        users_to_upgrade = UserStorage.objects.filter(
            max_storage=old_storage_limit,
            is_premium=False
        )

        count = users_to_upgrade.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ No users need upgrading!')
            )
            return

        self.stdout.write(f'📊 Found {count} users with 50MB limit')

        if not dry_run:
            # Update all at once
            updated = users_to_upgrade.update(max_storage=new_storage_limit)

            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(f'✅ Successfully upgraded {updated} users to 100MB!')
            )
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(f'Would upgrade {count} users (dry run)')
            )
            self.stdout.write('')
            self.stdout.write('Sample of users that would be upgraded:')
            for storage in users_to_upgrade[:10]:
                self.stdout.write(
                    f'  - {storage.user.username}: {storage.max_storage / (1024*1024):.0f}MB → 100MB'
                )
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')

        # Show current statistics
        self.stdout.write('')
        self.stdout.write('📈 Current Storage Distribution:')

        free_50mb = UserStorage.objects.filter(max_storage=old_storage_limit, is_premium=False).count()
        free_100mb = UserStorage.objects.filter(max_storage=new_storage_limit, is_premium=False).count()
        premium_users = UserStorage.objects.filter(is_premium=True).count()

        self.stdout.write(f'   Free 50MB: {free_50mb}')
        self.stdout.write(f'   Free 100MB: {free_100mb}')
        self.stdout.write(f'   Premium: {premium_users}')

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Command completed!')
        )

        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to apply changes')
            )

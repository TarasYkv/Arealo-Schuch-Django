"""
Management command to set up free plans for existing users
Run once: python manage.py setup_free_plans
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from videos.models import UserStorage
from videos.subscription_sync import StorageSubscriptionSync

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up free 100MB plans for all existing users who don\'t have UserStorage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Fix all users, even those with existing storage',
        )

    def handle(self, *args, **options):
        fix_all = options['fix_all']
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up free plans for users...')
        )
        
        total_users = User.objects.count()
        created_count = 0
        updated_count = 0
        
        for user in User.objects.all():
            try:
                user_storage, created = UserStorage.objects.get_or_create(
                    user=user,
                    defaults={
                        'used_storage': 0,
                        'max_storage': 104857600,  # 100MB
                        'is_premium': False,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'✅ Created free storage for: {user.username}')
                    
                elif fix_all:
                    # Sync with Stripe to ensure correct plan
                    StorageSubscriptionSync.sync_user_storage(user)
                    updated_count += 1
                    self.stdout.write(f'🔄 Synced storage for: {user.username}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to setup storage for {user.username}: {str(e)}')
                )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('📊 Summary:')
        )
        self.stdout.write(f'   Total users: {total_users}')
        self.stdout.write(f'   Free plans created: {created_count}')
        if fix_all:
            self.stdout.write(f'   Storage synced: {updated_count}')
        
        # Show current statistics
        free_users = UserStorage.objects.filter(is_premium=False).count()
        premium_users = UserStorage.objects.filter(is_premium=True).count()
        
        self.stdout.write('')
        self.stdout.write('📈 Current Plan Distribution:')
        self.stdout.write(f'   Free plans: {free_users}')
        self.stdout.write(f'   Premium plans: {premium_users}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Free plan setup completed!')
        )
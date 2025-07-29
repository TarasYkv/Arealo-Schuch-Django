"""
Daily storage maintenance command
Run this as a cron job: python manage.py storage_maintenance
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from videos.storage_management import StorageOverageService, VideoArchivingService
from videos.models import UserStorage
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Daily storage maintenance: check overages, apply restrictions, archive videos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--force-archiving',
            action='store_true',
            help='Force archiving for users at restriction level 3+',
        )
        parser.add_argument(
            '--cleanup-expired',
            action='store_true',
            help='Clean up videos archived for more than 90 days',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_archiving = options['force_archiving']
        cleanup_expired = options['cleanup_expired']
        
        self.stdout.write(
            self.style.SUCCESS('🔄 Starting daily storage maintenance...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  DRY RUN MODE - No changes will be made')
            )
        
        # Step 1: Check storage overage for all users
        self.stdout.write('\n📊 Step 1: Checking storage overage for all users...')
        
        if not dry_run:
            overaged_users, notifications_sent = StorageOverageService.check_all_users_storage()
            self.stdout.write(
                f'✅ Found {overaged_users} users with storage overage'
            )
            self.stdout.write(
                f'📧 Sent {notifications_sent} notifications'
            )
        else:
            # Dry run - just count
            overaged_count = UserStorage.objects.filter(
                used_storage__gt=models.F('max_storage')
            ).count()
            self.stdout.write(
                f'📊 Would check {UserStorage.objects.count()} users, {overaged_count} currently overaged'
            )
        
        # Step 2: Escalate restrictions
        self.stdout.write('\n⚡ Step 2: Escalating restrictions for long-term overages...')
        
        if not dry_run:
            escalated_users = StorageOverageService.escalate_restrictions_for_overaged_users()
            self.stdout.write(
                f'🔒 Escalated restrictions for {escalated_users} users'
            )
        else:
            # Count users who would get escalated restrictions
            eligible_users = UserStorage.objects.filter(
                overage_restriction_level__gt=0,
                overage_restriction_level__lt=3,
                used_storage__gt=models.F('max_storage')
            ).count()
            self.stdout.write(
                f'📊 Would escalate restrictions for up to {eligible_users} users'
            )
        
        # Step 3: Archive videos for users at restriction level 3+
        self.stdout.write('\n🗄️  Step 3: Archiving videos for severely overaged users...')
        
        users_for_archiving = UserStorage.objects.filter(
            overage_restriction_level__gte=3
        ).select_related('user')
        
        if force_archiving:
            users_for_archiving = UserStorage.objects.filter(
                overage_restriction_level__gt=0,
                used_storage__gt=models.F('max_storage')
            ).select_related('user')
        
        archived_total = 0
        for storage in users_for_archiving:
            user = storage.user
            overage_mb = storage.get_overage_amount_mb()
            
            if overage_mb > 0:
                self.stdout.write(
                    f'🗄️  Processing {user.username} (overage: {overage_mb:.1f}MB)...'
                )
                
                if not dry_run:
                    success, message = VideoArchivingService.archive_videos_for_user(
                        user, overage_mb + 10  # Archive a bit extra for buffer
                    )
                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'   ✅ {message}')
                        )
                        archived_total += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'   ❌ {message}')
                        )
                else:
                    # Dry run - show what would be archived
                    archivable_videos = VideoArchivingService.get_archivable_videos_for_user(
                        user, overage_mb + 10
                    )
                    video_count = len(archivable_videos)
                    total_mb = sum(v['size_mb'] for v in archivable_videos)
                    self.stdout.write(
                        f'   📊 Would archive {video_count} videos ({total_mb:.1f}MB)'
                    )
        
        if not dry_run:
            self.stdout.write(
                f'🗄️  Completed archiving for {archived_total} users'
            )
        
        # Step 4: Cleanup expired archives (if requested)
        if cleanup_expired:
            self.stdout.write('\n🗑️  Step 4: Cleaning up expired archived videos...')
            
            if not dry_run:
                deleted_count = VideoArchivingService.cleanup_expired_archives()
                self.stdout.write(
                    f'🗑️  Permanently deleted {deleted_count} expired archived videos'
                )
            else:
                from videos.models import Video
                expired_count = Video.objects.filter(
                    status='archived',
                    archive_expires_at__lt=timezone.now()
                ).count()
                self.stdout.write(
                    f'📊 Would permanently delete {expired_count} expired archived videos'
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('✅ Daily storage maintenance completed!')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  This was a dry run - no changes were made')
            )
            self.stdout.write(
                'Run without --dry-run to apply changes'
            )
        
        # Additional stats
        total_users = UserStorage.objects.count()
        overaged_users_count = UserStorage.objects.filter(
            used_storage__gt=models.F('max_storage')
        ).count()
        restricted_users_count = UserStorage.objects.filter(
            overage_restriction_level__gt=0
        ).count()
        
        self.stdout.write(f'\n📊 Current Statistics:')
        self.stdout.write(f'   Total users: {total_users}')
        self.stdout.write(f'   Users over storage limit: {overaged_users_count}')
        self.stdout.write(f'   Users with restrictions: {restricted_users_count}')
        
        self.stdout.write('\n💡 Recommended cron schedule:')
        self.stdout.write('   Daily: python manage.py storage_maintenance')
        self.stdout.write('   Weekly: python manage.py storage_maintenance --cleanup-expired')
        self.stdout.write('   Emergency: python manage.py storage_maintenance --force-archiving')
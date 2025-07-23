from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Sum
from videos.models import Video, UserStorage

User = get_user_model()


class Command(BaseCommand):
    help = 'Manage user storage quotas and usage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate storage usage for all users',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Specific username to manage',
        )
        parser.add_argument(
            '--set-quota',
            type=int,
            help='Set storage quota in MB',
        )
        parser.add_argument(
            '--list-usage',
            action='store_true',
            help='List storage usage for all users',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove storage records for users without videos',
        )

    def handle(self, *args, **options):
        if options['recalculate']:
            self.recalculate_storage()
        elif options['list_usage']:
            self.list_storage_usage()
        elif options['cleanup']:
            self.cleanup_storage()
        elif options['user'] and options['set_quota']:
            self.set_user_quota(options['user'], options['set_quota'])
        elif options['user']:
            self.show_user_info(options['user'])
        else:
            self.stdout.write(self.style.ERROR('Please specify an action. Use --help for options.'))

    def recalculate_storage(self):
        """Recalculate storage usage for all users"""
        self.stdout.write('Recalculating storage usage...')
        
        users_with_videos = User.objects.filter(videos__isnull=False).distinct()
        updated_count = 0
        
        for user in users_with_videos:
            total_size = Video.objects.filter(user=user).aggregate(
                total=Sum('file_size')
            )['total'] or 0
            
            user_storage, created = UserStorage.objects.get_or_create(user=user)
            old_usage = user_storage.used_storage
            user_storage.used_storage = total_size
            user_storage.save()
            
            if old_usage != total_size:
                updated_count += 1
                self.stdout.write(
                    f'Updated {user.username}: {old_usage/1024/1024:.2f} MB → {total_size/1024/1024:.2f} MB'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Storage recalculated for {updated_count} users.')
        )

    def list_storage_usage(self):
        """List storage usage for all users"""
        storage_records = UserStorage.objects.select_related('user').all()
        
        self.stdout.write('\nBenutzer-Speicherplatz-Übersicht:')
        self.stdout.write('-' * 80)
        self.stdout.write(f'{"Username":<20} {"Belegt":<12} {"Limit":<12} {"Auslastung":<12} {"Premium":<8}')
        self.stdout.write('-' * 80)
        
        for storage in storage_records:
            used_mb = storage.get_used_storage_mb()
            max_mb = storage.get_max_storage_mb()
            percentage = (storage.used_storage / storage.max_storage * 100) if storage.max_storage > 0 else 0
            premium = "Ja" if storage.is_premium else "Nein"
            
            self.stdout.write(
                f'{storage.user.username:<20} '
                f'{used_mb:<8.2f} MB '
                f'{max_mb:<8.2f} MB '
                f'{percentage:<8.1f}% '
                f'{premium:<8}'
            )
        
        total_users = storage_records.count()
        premium_users = storage_records.filter(is_premium=True).count()
        
        self.stdout.write('-' * 80)
        self.stdout.write(f'Gesamt: {total_users} Benutzer ({premium_users} Premium)')

    def set_user_quota(self, username, quota_mb):
        """Set storage quota for a specific user"""
        try:
            user = User.objects.get(username=username)
            user_storage, created = UserStorage.objects.get_or_create(user=user)
            
            old_quota = user_storage.get_max_storage_mb()
            user_storage.max_storage = quota_mb * 1024 * 1024  # Convert MB to bytes
            user_storage.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Speicherplatz für {username} geändert: '
                    f'{old_quota:.2f} MB → {quota_mb} MB'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Benutzer "{username}" nicht gefunden.')
            )

    def show_user_info(self, username):
        """Show detailed info for a specific user"""
        try:
            user = User.objects.get(username=username)
            user_storage, created = UserStorage.objects.get_or_create(user=user)
            
            videos = Video.objects.filter(user=user)
            video_count = videos.count()
            
            self.stdout.write(f'\nBenutzer-Info für: {username}')
            self.stdout.write('-' * 40)
            self.stdout.write(f'Videos: {video_count}')
            self.stdout.write(f'Belegter Speicher: {user_storage.get_used_storage_mb():.2f} MB')
            self.stdout.write(f'Maximaler Speicher: {user_storage.get_max_storage_mb():.2f} MB')
            percentage = (user_storage.used_storage / user_storage.max_storage * 100) if user_storage.max_storage > 0 else 0
            self.stdout.write(f'Auslastung: {percentage:.1f}%')
            self.stdout.write(f'Premium: {"Ja" if user_storage.is_premium else "Nein"}')
            
            if video_count > 0:
                self.stdout.write('\nVideos:')
                for video in videos:
                    self.stdout.write(f'  - {video.title}: {video.file_size/1024/1024:.2f} MB')
                    
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Benutzer "{username}" nicht gefunden.')
            )

    def cleanup_storage(self):
        """Remove storage records for users without videos"""
        empty_storage = UserStorage.objects.filter(used_storage=0, user__videos__isnull=True)
        count = empty_storage.count()
        
        if count > 0:
            empty_storage.delete()
            self.stdout.write(
                self.style.SUCCESS(f'{count} leere Speicherplatz-Einträge entfernt.')
            )
        else:
            self.stdout.write('Keine leeren Speicherplatz-Einträge gefunden.')
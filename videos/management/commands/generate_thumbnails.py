from django.core.management.base import BaseCommand
from videos.models import Video
from videos.utils import generate_video_thumbnail


class Command(BaseCommand):
    help = 'Generate thumbnails for existing videos that don\'t have them'

    def handle(self, *args, **options):
        videos_without_thumbnails = Video.objects.filter(thumbnail='')
        total = videos_without_thumbnails.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('All videos already have thumbnails!'))
            return
        
        self.stdout.write(f'Found {total} videos without thumbnails.')
        
        success_count = 0
        for i, video in enumerate(videos_without_thumbnails, 1):
            try:
                self.stdout.write(f'[{i}/{total}] Generating thumbnail for: {video.title}')
                generate_video_thumbnail(video)
                video.save()
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Generated thumbnail for: {video.title}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed to generate thumbnail for {video.title}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nCompleted! Generated {success_count}/{total} thumbnails.'))
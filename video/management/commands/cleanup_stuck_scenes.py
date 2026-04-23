from django.core.management.base import BaseCommand
from django.utils import timezone
from video.models import Scene
from datetime import timedelta


class Command(BaseCommand):
    help = 'Reset scenes stuck in generating status for more than N minutes'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=10, help='Minutes before reset (default: 10)')

    def handle(self, *args, **options):
        timeout_minutes = options['timeout']
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
        
        stuck = Scene.objects.filter(status='generating', created_at__lt=cutoff)
        count = stuck.count()
        
        for s in stuck:
            s.status = 'error'
            s.error_message = f'Auto-cancelled: stuck for {timeout_minutes}+ min'
            s.save()
        
        self.stdout.write(f'Reset {count} stuck scenes.')

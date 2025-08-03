"""
Django management command to migrate DALL-E images to local storage
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from makeads.image_utils import batch_migrate_dalle_images
from makeads.models import Creative
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate DALL-E images from external URLs to local storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of images to process',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        self.stdout.write("🖼️  MakeAds DALL-E Image Migration Tool")
        self.stdout.write("=" * 50)
        
        # Count creatives that need migration
        creatives_to_migrate = Creative.objects.filter(
            image_url__isnull=False
        ).exclude(image_url='').filter(
            models.Q(image_file__isnull=True) | models.Q(image_file='')
        )
        
        if options['limit']:
            creatives_to_migrate = creatives_to_migrate[:options['limit']]
        
        total_count = creatives_to_migrate.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ No creatives need migration - all images are already local!")
            )
            return
        
        self.stdout.write(f"📊 Found {total_count} creatives with external image URLs")
        
        if options['dry_run']:
            self.stdout.write("\n🔍 DRY RUN MODE - No changes will be made\n")
            for creative in creatives_to_migrate[:10]:  # Show first 10
                self.stdout.write(f"   Would migrate: {creative.title} ({creative.id})")
                self.stdout.write(f"   URL: {creative.image_url[:80]}...")
            
            if total_count > 10:
                self.stdout.write(f"   ... and {total_count - 10} more")
            return
        
        # Confirm before proceeding
        if not options.get('force', False):
            confirm = input(f"\n⚠️  This will download {total_count} images. Continue? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("❌ Migration cancelled")
                return
        
        # Start migration
        self.stdout.write(f"\n🚀 Starting migration of {total_count} images...")
        start_time = timezone.now()
        
        try:
            success_count, fail_count = batch_migrate_dalle_images()
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("📈 Migration Results:")
            self.stdout.write(f"   ✅ Successfully migrated: {success_count}")
            self.stdout.write(f"   ❌ Failed: {fail_count}")
            self.stdout.write(f"   ⏱️  Duration: {duration:.1f} seconds")
            
            if success_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"\n🎉 Migration completed! {success_count} images now stored locally.")
                )
            
            if fail_count > 0:
                self.stdout.write(
                    self.style.WARNING(f"\n⚠️  {fail_count} images could not be migrated (URLs may be expired).")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n💥 Migration failed with error: {str(e)}")
            )
            logger.error(f"DALL-E migration error: {str(e)}")
            raise
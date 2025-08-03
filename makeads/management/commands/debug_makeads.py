"""
Django Management Command für MakeAds Debugging

Verwendung:
    python manage.py debug_makeads
    python manage.py debug_makeads --user-id 1
    python manage.py debug_makeads --test-images
    python manage.py debug_makeads --test-text
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from makeads.debug_tools import debug_api_keys, test_image_generation, test_text_generation, run_full_debug

User = get_user_model()


class Command(BaseCommand):
    help = 'Debuggt die MakeAds API-Key Konfiguration und testet die Bild-/Textgenerierung'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID für den Test (optional, verwendet ersten User wenn nicht angegeben)',
        )
        parser.add_argument(
            '--test-images',
            action='store_true',
            help='Testet nur die Bildgenerierung',
        )
        parser.add_argument(
            '--test-text',
            action='store_true',
            help='Testet nur die Textgenerierung',
        )
        parser.add_argument(
            '--api-keys-only',
            action='store_true',
            help='Testet nur die API-Key Konfiguration',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        test_images = options.get('test_images')
        test_text = options.get('test_text')
        api_keys_only = options.get('api_keys_only')

        self.stdout.write(
            self.style.SUCCESS('🚀 MakeAds Debug Command gestartet')
        )

        try:
            if api_keys_only:
                # Nur API-Keys testen
                debug_api_keys(user_id)
            elif test_images:
                # Nur Bildgenerierung testen
                test_image_generation(user_id)
            elif test_text:
                # Nur Textgenerierung testen
                test_text_generation(user_id)
            else:
                # Vollständiger Test
                run_full_debug(user_id)

            self.stdout.write(
                self.style.SUCCESS('\n✅ Debug-Tests abgeschlossen')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Fehler beim Debugging: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())
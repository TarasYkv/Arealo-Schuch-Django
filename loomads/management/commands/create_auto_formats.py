from django.core.management.base import BaseCommand
from django.utils import timezone
from loomads.models import AutoCampaignFormat


class Command(BaseCommand):
    help = 'Creates additional auto-campaign formats to cover more ad zones'

    def handle(self, *args, **options):
        self.stdout.write('Creating additional auto-campaign formats...')
        
        formats_created = []
        formats_updated = []
        
        # 1. Video-Format-Bundle (640x360, 600x400)
        video_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='video_preroll_640x360',
            defaults={
                'name': 'Video-Format Bundle',
                'description': 'Alle Video Pre-Roll und End-Screen Formate',
                'target_zone_types': ['video_preroll', 'video_popup'],
                'target_dimensions': ['640x360', '600x400'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 9,
                'is_active': True
            }
        )
        if created:
            formats_created.append(video_format.name)
        else:
            formats_updated.append(video_format.name)
        
        # 2. Modal-Format (400x300, 450x350, 500x400)
        modal_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='modal_400x300',
            defaults={
                'name': 'Modal & Popup Format',
                'description': 'Alle Modal und Popup Formate verschiedener Größen',
                'target_zone_types': ['modal'],
                'target_dimensions': ['400x300', '450x350', '500x400'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 7,
                'is_active': True
            }
        )
        if created:
            formats_created.append(modal_format.name)
        else:
            formats_updated.append(modal_format.name)
        
        # 3. Benachrichtigungs-Format (300x80, 350x80, 400x80, 500x80)
        notification_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='notification_300x80',
            defaults={
                'name': 'Benachrichtigungs-Format',
                'description': 'Alle Benachrichtigungs-Banner verschiedener Breiten',
                'target_zone_types': ['notification'],
                'target_dimensions': ['300x80', '350x80', '400x80', '500x80'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 6,
                'is_active': True
            }
        )
        if created:
            formats_created.append(notification_format.name)
        else:
            formats_updated.append(notification_format.name)
        
        # 4. Erweiterte Seitenleisten (300x400, 300x500, 300x600)
        extended_sidebar_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Erweiterte Seitenleisten',
            defaults={
                'description': 'Große Seitenleisten-Formate für Tools und Studios',
                'target_zone_types': ['sidebar'],
                'target_dimensions': ['300x400', '300x500', '300x600'],
                'grouping_strategy': 'by_dimensions',
                'priority': 5,
                'is_active': True
            }
        )
        if created:
            formats_created.append(extended_sidebar_format.name)
        else:
            formats_updated.append(extended_sidebar_format.name)
        
        # 5. Video-Overlay-Format (300x100, 320x100, 350x120)
        video_overlay_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='video_overlay_300x100',
            defaults={
                'name': 'Video Overlay Format',
                'description': 'Video Overlay Banner verschiedener Breiten',
                'target_zone_types': ['video_overlay'],
                'target_dimensions': ['300x100', '320x100', '350x120'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 8,
                'is_active': True
            }
        )
        if created:
            formats_created.append(video_overlay_format.name)
        else:
            formats_updated.append(video_overlay_format.name)
        
        # 6. Große In-Feed-Format (728x250)
        large_infeed_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Große In-Feed Format',
            defaults={
                'description': 'Große In-Feed Anzeigen für prominente Platzierungen',
                'target_zone_types': ['in_feed'],
                'target_dimensions': ['728x250'],
                'grouping_strategy': 'by_dimensions',
                'priority': 7,
                'is_active': True
            }
        )
        if created:
            formats_created.append(large_infeed_format.name)
        else:
            formats_updated.append(large_infeed_format.name)
        
        # 7. Content Card Varianten (350x200, 350x250)
        content_card_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='content_card_350x250',
            defaults={
                'name': 'Content Card Format (Erweitert)',
                'description': 'Erweiterte Content Card Formate',
                'target_zone_types': ['content_card'],
                'target_dimensions': ['350x200', '350x250'],
                'grouping_strategy': 'by_type_and_dimensions',
                'priority': 6,
                'is_active': True
            }
        )
        if created:
            formats_created.append(content_card_format.name)
        else:
            formats_updated.append(content_card_format.name)
        
        # 8. Spezial Header/Footer (320x100, 600x100)
        special_banner_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Spezial Banner Format',
            defaults={
                'description': 'Spezielle Banner-Formate für verschiedene Breiten',
                'target_zone_types': ['header', 'footer'],
                'target_dimensions': ['320x100', '600x100'],
                'grouping_strategy': 'by_dimensions',
                'priority': 4,
                'is_active': True
            }
        )
        if created:
            formats_created.append(special_banner_format.name)
        else:
            formats_updated.append(special_banner_format.name)
        
        # 9. Audio/Stream Overlay (350x120, 400x150)
        audio_overlay_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Audio/Stream Overlay Format',
            defaults={
                'description': 'Overlay-Formate für Audio und Stream Anwendungen',
                'target_zone_types': ['video_overlay'],
                'target_dimensions': ['350x120', '400x150'],
                'grouping_strategy': 'by_dimensions',
                'priority': 5,
                'is_active': True
            }
        )
        if created:
            formats_created.append(audio_overlay_format.name)
        else:
            formats_updated.append(audio_overlay_format.name)
        
        # 10. Kompakte Karten (320x240, 300x200)
        compact_card_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Kompakte Karten Format',
            defaults={
                'description': 'Kleinere Karten-Formate für verschiedene Anwendungen',
                'target_zone_types': ['content_card', 'in_feed'],
                'target_dimensions': ['320x240', '300x200'],
                'grouping_strategy': 'by_dimensions',
                'priority': 5,
                'is_active': True
            }
        )
        if created:
            formats_created.append(compact_card_format.name)
        else:
            formats_updated.append(compact_card_format.name)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Auto-Format Erstellung abgeschlossen ==='))
        
        if formats_created:
            self.stdout.write(self.style.SUCCESS(f'\nErfolgreich erstellt ({len(formats_created)} Formate):'))
            for name in formats_created:
                self.stdout.write(f'  ✓ {name}')
        
        if formats_updated:
            self.stdout.write(self.style.WARNING(f'\nBereits vorhanden ({len(formats_updated)} Formate):'))
            for name in formats_updated:
                self.stdout.write(f'  • {name}')
        
        # Statistik
        total_formats = AutoCampaignFormat.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f'\n=== Gesamt aktive Auto-Formate: {total_formats} ==='))
        
        # Zone-Abdeckung berechnen
        total_zone_coverage = 0
        for format_obj in AutoCampaignFormat.objects.filter(is_active=True):
            zone_count = format_obj.get_zone_count()
            total_zone_coverage += zone_count
            self.stdout.write(f'  {format_obj.name}: {zone_count} Zonen')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Geschätzte Gesamt-Zonenabdeckung: ~{total_zone_coverage} Zonen ==='))
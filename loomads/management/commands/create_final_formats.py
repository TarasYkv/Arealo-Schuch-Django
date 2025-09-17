from django.core.management.base import BaseCommand
from loomads.models import AutoCampaignFormat, AdZone


class Command(BaseCommand):
    help = 'Creates final auto-formats to cover remaining zones'

    def handle(self, *args, **options):
        self.stdout.write('Creating final auto-formats for complete coverage...')
        
        formats_created = []
        formats_updated = []
        
        # 1. Mixed Sidebar Format (320x400)
        mixed_sidebar_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Mixed Sidebar Format',
            defaults={
                'description': 'Seitenleisten mit speziellen Breiten',
                'target_zone_types': ['sidebar'],
                'target_dimensions': ['320x400'],
                'grouping_strategy': 'by_dimensions',
                'priority': 4,
                'is_active': True
            }
        )
        if created:
            formats_created.append(mixed_sidebar_format.name)
        else:
            formats_updated.append(mixed_sidebar_format.name)
        
        # 2. Content Card Special (600x400, 400x300)
        special_content_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Content Card Special Format',
            defaults={
                'description': 'Spezielle Content Card Formate',
                'target_zone_types': ['content_card', 'modal'],
                'target_dimensions': ['600x400', '400x300'],
                'grouping_strategy': 'by_dimensions',
                'priority': 5,
                'is_active': True
            }
        )
        if created:
            formats_created.append(special_content_format.name)
        else:
            formats_updated.append(special_content_format.name)
        
        # 3. Wide Notification Format (600x100)
        wide_notification_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Wide Notification Format',
            defaults={
                'description': 'Breite Benachrichtigungs-Banner',
                'target_zone_types': ['notification', 'header'],
                'target_dimensions': ['600x100'],
                'grouping_strategy': 'by_dimensions',
                'priority': 4,
                'is_active': True
            }
        )
        if created:
            formats_created.append(wide_notification_format.name)
        else:
            formats_updated.append(wide_notification_format.name)
        
        # 4. Mixed Video Formats (350x250 for video_popup, 350x200 for video_overlay)
        mixed_video_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Mixed Video Formats',
            defaults={
                'description': 'Gemischte Video-Formate für verschiedene Anwendungen',
                'target_zone_types': ['video_popup', 'video_overlay', 'content_card'],
                'target_dimensions': ['350x250', '350x200'],
                'grouping_strategy': 'by_dimensions',
                'priority': 6,
                'is_active': True
            }
        )
        if created:
            formats_created.append(mixed_video_format.name)
        else:
            formats_updated.append(mixed_video_format.name)
        
        # 5. Universal Footer Format (728x90 for content_card type)
        universal_footer_format, created = AutoCampaignFormat.objects.get_or_create(
            format_type='custom',
            name='Universal Footer Format',
            defaults={
                'description': 'Universelles Footer-Format für verschiedene Zone-Typen',
                'target_zone_types': ['content_card', 'footer', 'header'],
                'target_dimensions': ['728x90'],
                'grouping_strategy': 'by_dimensions',
                'priority': 8,
                'is_active': True
            }
        )
        if created:
            formats_created.append(universal_footer_format.name)
        else:
            formats_updated.append(universal_footer_format.name)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Final Auto-Format Erstellung abgeschlossen ==='))
        
        if formats_created:
            self.stdout.write(self.style.SUCCESS(f'\nErfolgreich erstellt ({len(formats_created)} Formate):'))
            for name in formats_created:
                self.stdout.write(f'  ✓ {name}')
        
        if formats_updated:
            self.stdout.write(self.style.WARNING(f'\nBereits vorhanden ({len(formats_updated)} Formate):'))
            for name in formats_updated:
                self.stdout.write(f'  • {name}')
        
        # Final coverage check
        self.stdout.write('\n=== FINALE ABDECKUNGSANALYSE ===')
        
        total_zones = AdZone.objects.filter(is_active=True).count()
        all_covered_zones = set()
        
        for fmt in AutoCampaignFormat.objects.filter(is_active=True):
            zones = fmt.get_matching_zones()
            for zone in zones:
                all_covered_zones.add(zone.id)
        
        covered_count = len(all_covered_zones)
        coverage_percentage = (covered_count / total_zones * 100) if total_zones > 0 else 0
        
        self.stdout.write(self.style.SUCCESS(f'\nGesamtzonen: {total_zones}'))
        self.stdout.write(self.style.SUCCESS(f'Abgedeckte Zonen: {covered_count}'))
        self.stdout.write(self.style.SUCCESS(f'Abdeckungsrate: {coverage_percentage:.1f}%'))
        
        # List remaining uncovered zones if any
        not_covered = AdZone.objects.filter(is_active=True).exclude(id__in=all_covered_zones)
        if not_covered.exists():
            self.stdout.write(self.style.WARNING(f'\nNoch nicht abgedeckte Zonen ({not_covered.count()}):'))
            for zone in not_covered:
                self.stdout.write(f'  - {zone.name} ({zone.width}x{zone.height}, Type: {zone.zone_type})')
        else:
            self.stdout.write(self.style.SUCCESS('\n🎉 ALLE ZONEN SIND JETZT ABGEDECKT!'))
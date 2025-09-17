from django.core.management.base import BaseCommand
from loomads.models import AdZone


class Command(BaseCommand):
    help = 'Creates missing ad zones based on hardcoded examples to match auto-formats'

    def handle(self, *args, **options):
        self.stdout.write('Creating missing ad zones...')
        
        zones_created = []
        zones_updated = []
        
        # Define all zones that should exist based on hardcoded_examples.py
        zones_data = [
            # Existing zones (will be skipped if they exist)
            {'code': 'header_main', 'name': 'Header Hauptbanner', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'footer_main', 'name': 'Footer Banner', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'sidebar_main', 'name': 'Haupt-Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 250},
            {'code': 'content_infeed', 'name': 'Content In-Feed', 'zone_type': 'in_feed', 'width': 300, 'height': 200},
            {'code': 'popup_welcome', 'name': 'Willkommen Pop-up', 'zone_type': 'modal', 'width': 400, 'height': 300},
            
            # Blog zones
            {'code': 'blog_header', 'name': 'Blog Header Zone', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'blog_footer', 'name': 'Blog Footer Zone', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'blog_post_ad', 'name': 'Blog Post Ad Block', 'zone_type': 'content_card', 'width': 350, 'height': 200},
            
            # Collection zones
            {'code': 'collection_header', 'name': 'Collection Header Zone', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'collection_footer', 'name': 'Collection Footer Zone', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'collection_ad', 'name': 'Collection Ad Block', 'zone_type': 'content_card', 'width': 350, 'height': 200},
            
            # Shopify zones
            {'code': 'shopify_header', 'name': 'Shopify Header Zone', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'shopify_footer', 'name': 'Shopify Footer Zone', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'shopify_infeed', 'name': 'Shopify In-Feed Zone', 'zone_type': 'in_feed', 'width': 728, 'height': 250},
            {'code': 'shopify_product', 'name': 'Shopify Product Ad Block', 'zone_type': 'content_card', 'width': 350, 'height': 200},
            
            # Video zones
            {'code': 'video_preroll_main', 'name': 'Video Pre-Roll Hauptbereich', 'zone_type': 'video_preroll', 'width': 640, 'height': 360},
            {'code': 'video_overlay_main', 'name': 'Video Overlay Hauptbereich', 'zone_type': 'video_overlay', 'width': 300, 'height': 100},
            {'code': 'video_popup_main', 'name': 'Video Popup - Hauptbereich', 'zone_type': 'video_popup', 'width': 350, 'height': 250},
            {'code': 'videos_header', 'name': 'Videos Header Banner', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'videos_sidebar', 'name': 'Videos Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 600},
            {'code': 'videos_sidebar_card', 'name': 'Videos Sidebar Karte', 'zone_type': 'sidebar', 'width': 300, 'height': 250},
            {'code': 'videos_content_overlay', 'name': 'Videos Content Overlay', 'zone_type': 'video_overlay', 'width': 320, 'height': 100},
            {'code': 'videos_footer', 'name': 'Videos Footer Banner', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'videos_modal', 'name': 'Videos Modal Pop-up', 'zone_type': 'modal', 'width': 500, 'height': 400},
            {'code': 'videos_recommendation', 'name': 'Videos Empfehlung Karte', 'zone_type': 'content_card', 'width': 320, 'height': 240},
            {'code': 'videos_player_overlay', 'name': 'Videos Player Overlay', 'zone_type': 'video_overlay', 'width': 350, 'height': 120},
            {'code': 'videos_preroll', 'name': 'Videos Pre-Roll', 'zone_type': 'video_preroll', 'width': 640, 'height': 360},
            {'code': 'videos_endscreen', 'name': 'Videos End Screen', 'zone_type': 'video_popup', 'width': 600, 'height': 400},
            {'code': 'videos_comment_sidebar', 'name': 'Videos Kommentar-Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 250},
            
            # StreamRec zones
            {'code': 'streamrec_header', 'name': 'StreamRec Recording Header', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'streamrec_studio_sidebar', 'name': 'StreamRec Studio Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 500},
            {'code': 'streamrec_control_overlay', 'name': 'StreamRec Steuerung Overlay', 'zone_type': 'video_overlay', 'width': 320, 'height': 100},
            {'code': 'streamrec_tips_sidebar', 'name': 'StreamRec Tipps Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 400},
            {'code': 'streamrec_tools_footer', 'name': 'StreamRec Tools Footer', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'streamrec_help_modal', 'name': 'StreamRec Hilfe Modal', 'zone_type': 'modal', 'width': 500, 'height': 400},
            {'code': 'streamrec_notification', 'name': 'StreamRec Benachrichtigung Banner', 'zone_type': 'notification', 'width': 350, 'height': 80},
            {'code': 'streamrec_audio_overlay', 'name': 'StreamRec Audio Overlay', 'zone_type': 'video_overlay', 'width': 350, 'height': 120},
            {'code': 'streamrec_video_overlay', 'name': 'StreamRec Video Overlay', 'zone_type': 'video_overlay', 'width': 400, 'height': 150},
            {'code': 'streamrec_download', 'name': 'StreamRec Download Seite', 'zone_type': 'modal', 'width': 400, 'height': 300},
            {'code': 'streamrec_processing', 'name': 'StreamRec Processing Banner', 'zone_type': 'notification', 'width': 400, 'height': 80},
            
            # PromptPro zones
            {'code': 'promptpro_tile', 'name': 'PromptPro Prompt Kachel', 'zone_type': 'content_card', 'width': 300, 'height': 200},
            {'code': 'promptpro_tools_sidebar', 'name': 'PromptPro Tools Seitenleiste', 'zone_type': 'sidebar', 'width': 300, 'height': 400},
            {'code': 'promptpro_category_banner', 'name': 'PromptPro Kategorie Banner', 'zone_type': 'header', 'width': 600, 'height': 100},
            {'code': 'promptpro_featured', 'name': 'PromptPro Featured Prompt', 'zone_type': 'content_card', 'width': 350, 'height': 250},
            {'code': 'promptpro_upgrade_modal', 'name': 'PromptPro Pro Upgrade Modal', 'zone_type': 'modal', 'width': 450, 'height': 350},
            {'code': 'promptpro_footer_cta', 'name': 'PromptPro Footer Call-to-Action', 'zone_type': 'footer', 'width': 728, 'height': 90},
            {'code': 'promptpro_tip_notification', 'name': 'PromptPro Tipp Benachrichtigung', 'zone_type': 'notification', 'width': 400, 'height': 80},
            {'code': 'promptpro_result_banner', 'name': 'PromptPro Ergebnis Banner', 'zone_type': 'notification', 'width': 500, 'height': 80},
            {'code': 'promptpro_dashboard_header', 'name': 'PromptPro Dashboard Header', 'zone_type': 'header', 'width': 728, 'height': 90},
            {'code': 'promptpro_category_header', 'name': 'PromptPro Kategorie Header', 'zone_type': 'header', 'width': 600, 'height': 100},
            
            # Content Cards
            {'code': 'content_card_main', 'name': 'Content Card Hauptbereich', 'zone_type': 'content_card', 'width': 350, 'height': 250},
            
            # Notifications
            {'code': 'notification_main', 'name': 'Benachrichtigung Hauptbereich', 'zone_type': 'notification', 'width': 300, 'height': 80},
        ]
        
        for zone_data in zones_data:
            zone, created = AdZone.objects.get_or_create(
                code=zone_data['code'],
                defaults={
                    'name': zone_data['name'],
                    'zone_type': zone_data['zone_type'],
                    'width': zone_data['width'],
                    'height': zone_data['height'],
                    'description': f'Auto-created zone for {zone_data["name"]}',
                    'is_active': True,
                    'max_ads': 5
                }
            )
            
            if created:
                zones_created.append(zone.name)
            else:
                zones_updated.append(zone.name)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Zone-Erstellung abgeschlossen ==='))
        
        if zones_created:
            self.stdout.write(self.style.SUCCESS(f'\nErfolgreich erstellt ({len(zones_created)} Zonen):'))
            for name in zones_created:
                self.stdout.write(f'  ✓ {name}')
        
        if zones_updated:
            self.stdout.write(self.style.WARNING(f'\nBereits vorhanden ({len(zones_updated)} Zonen):'))
            for name in zones_updated:
                self.stdout.write(f'  • {name}')
        
        # Statistik
        total_zones = AdZone.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f'\n=== Gesamt aktive Zonen: {total_zones} ==='))
        
        # Zone types distribution
        from django.db.models import Count
        zone_types = AdZone.objects.filter(is_active=True).values('zone_type').annotate(count=Count('zone_type')).order_by('-count')
        self.stdout.write('\nVerteilung nach Zone-Typen:')
        for zt in zone_types:
            self.stdout.write(f'  {zt["zone_type"]}: {zt["count"]} Zonen')
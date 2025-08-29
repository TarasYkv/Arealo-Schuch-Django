from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from loomads.models import Campaign, AdZone, Advertisement, AdTargeting
import uuid

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates sample ad zones, campaigns and advertisements for LoomAds'

    def handle(self, *args, **options):
        # Get or create superuser
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            self.stdout.write(self.style.ERROR('No superuser found. Please create a superuser first.'))
            return

        self.stdout.write('Creating sample LoomAds data...')

        # Create Ad Zones
        zones_data = [
            {
                'code': 'header_main',
                'name': 'Header Hauptbanner',
                'description': 'Prominenter Banner im Header-Bereich',
                'zone_type': 'header',
                'width': 728,
                'height': 90,
            },
            {
                'code': 'sidebar_main',
                'name': 'Haupt-Seitenleiste',
                'description': 'Standard Werbeplatz in der Seitenleiste',
                'zone_type': 'sidebar',
                'width': 300,
                'height': 250,
            },
            {
                'code': 'content_infeed',
                'name': 'Content In-Feed',
                'description': 'Anzeige zwischen Content-Elementen',
                'zone_type': 'in_feed',
                'width': 300,
                'height': 200,
            },
            {
                'code': 'footer_main',
                'name': 'Footer Banner',
                'description': 'Banner am Ende der Seite',
                'zone_type': 'footer',
                'width': 728,
                'height': 90,
            },
            {
                'code': 'popup_welcome',
                'name': 'Willkommen Pop-up',
                'description': 'Pop-up für neue Besucher',
                'zone_type': 'modal',
                'width': 400,
                'height': 300,
            }
        ]

        zones = []
        for zone_data in zones_data:
            zone, created = AdZone.objects.get_or_create(
                code=zone_data['code'],
                defaults=zone_data
            )
            zones.append(zone)
            status = "Created" if created else "Exists"
            self.stdout.write(f'  {status}: Zone "{zone.name}" ({zone.code})')

        # Create Sample Campaign
        campaign, created = Campaign.objects.get_or_create(
            name='Workloom Feature Promotion',
            defaults={
                'description': 'Bewerbung neuer Workloom Features und Funktionen',
                'status': 'active',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=30),
                'created_by': superuser,
                'daily_impression_limit': 1000,
                'total_impression_limit': 30000,
            }
        )
        status = "Created" if created else "Updated"
        self.stdout.write(f'  {status}: Campaign "{campaign.name}"')

        # Create Sample Advertisements
        ads_data = [
            {
                'name': 'Naturmacher Feature Banner',
                'ad_type': 'html',
                'title': 'Entdecke Naturmacher!',
                'description': 'Erstelle KI-basierte Schulungen mit unserem neuen Tool',
                'html_content': '''
                <div style="background: linear-gradient(135deg, #4CAF50, #2E7D32); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3 style="margin: 0 0 10px 0;">🌿 Naturmacher</h3>
                    <p style="margin: 0 0 15px 0;">KI-gestützte Schulungserstellung</p>
                    <button style="background: white; color: #2E7D32; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Jetzt entdecken!</button>
                </div>
                ''',
                'target_url': '/naturmacher/',
                'weight': 8,
            },
            {
                'name': 'Streamrec Audio Studio Promo',
                'ad_type': 'html',
                'title': 'Audio Studio by Streamrec',
                'description': 'Professionelle Audioaufnahmen direkt im Browser',
                'html_content': '''
                <div style="background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px; border-radius: 8px;">
                    <h4 style="margin: 0 0 8px 0;">🎙️ Audio Studio</h4>
                    <p style="margin: 0 0 10px 0; font-size: 14px;">Professionelle Aufnahmen</p>
                    <small>Jetzt kostenlos testen!</small>
                </div>
                ''',
                'target_url': '/streamrec/',
                'weight': 6,
            },
            {
                'name': 'MakeAds Creator Highlight',
                'ad_type': 'html',
                'title': 'MakeAds - KI Werbung',
                'description': 'Erstelle professionelle Werbeanzeigen mit KI',
                'html_content': '''
                <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 18px; border-radius: 8px;">
                    <h4 style="margin: 0 0 10px 0;">🎨 MakeAds</h4>
                    <p style="margin: 0; font-size: 13px;">KI-basierte Werbeerstellung</p>
                </div>
                ''',
                'target_url': '/makeads/',
                'weight': 7,
            },
            {
                'name': 'CodeLib Development Tools',
                'ad_type': 'text',
                'title': 'CodeLib - Developer Tools',
                'description': 'Entwickler-Tools und Code-Bibliotheken für deine Projekte. Steigere deine Produktivität mit unseren bewährten Lösungen.',
                'target_url': '/codelib/',
                'weight': 5,
            },
        ]

        for ad_data in ads_data:
            ad, created = Advertisement.objects.get_or_create(
                name=ad_data['name'],
                defaults={
                    **ad_data,
                    'campaign': campaign,
                }
            )
            if created:
                # Add to appropriate zones based on ad type
                if 'Banner' in ad.name:
                    ad.zones.add(zones[0])  # header_main
                elif 'Promo' in ad.name:
                    ad.zones.add(zones[1])  # sidebar_main
                elif 'Highlight' in ad.name:
                    ad.zones.add(zones[2])  # content_infeed
                else:
                    ad.zones.add(zones[1], zones[2])  # sidebar and infeed

                # Create targeting
                targeting = AdTargeting.objects.create(
                    advertisement=ad,
                    target_desktop=True,
                    target_mobile=True,
                    target_tablet=True,
                    target_logged_in=True,
                    target_anonymous=True,
                )
                
            status = "Created" if created else "Exists"
            self.stdout.write(f'  {status}: Ad "{ad.name}"')

        # Create a Modal/Pop-up Ad
        popup_ad, created = Advertisement.objects.get_or_create(
            name='Workloom Welcome Modal',
            defaults={
                'campaign': campaign,
                'ad_type': 'html',
                'title': 'Willkommen bei Workloom!',
                'description': 'Entdecke alle Features unserer Plattform',
                'html_content': '''
                <div style="text-align: center; padding: 30px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
                    <h2 style="color: #333; margin-bottom: 15px;">🚀 Willkommen bei Workloom!</h2>
                    <p style="color: #666; margin-bottom: 20px;">Entdecke alle Funktionen unserer All-in-One Business Platform</p>
                    <div style="display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;">
                        <span style="background: #4CAF50; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">📊 Analytics</span>
                        <span style="background: #2196F3; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">🎙️ Audio Studio</span>
                        <span style="background: #FF9800; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">🎨 MakeAds</span>
                    </div>
                    <button style="margin-top: 20px; background: #4CAF50; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold;">Los geht's!</button>
                </div>
                ''',
                'target_url': '/accounts/dashboard/',
                'weight': 10,
            }
        )
        
        if created:
            popup_ad.zones.add(zones[4])  # popup_welcome
            AdTargeting.objects.create(
                advertisement=popup_ad,
                target_desktop=True,
                target_mobile=True,
                target_tablet=True,
                target_logged_in=False,  # Only for anonymous users
                target_anonymous=True,
            )

        status = "Created" if created else "Exists"
        self.stdout.write(f'  {status}: Modal Ad "{popup_ad.name}"')

        self.stdout.write(self.style.SUCCESS('Successfully created sample LoomAds data!'))
        self.stdout.write('')
        self.stdout.write('Created:')
        self.stdout.write(f'  • {len(zones)} Ad Zones')
        self.stdout.write(f'  • 1 Campaign')
        self.stdout.write(f'  • {Advertisement.objects.filter(campaign=campaign).count()} Advertisements')
        self.stdout.write('')
        self.stdout.write('You can now:')
        self.stdout.write('  • Visit /admin/loomads/ to manage ads')
        self.stdout.write('  • Visit /loomads/ to see the dashboard')
        self.stdout.write('  • Add template tags to integrate ads in your templates')
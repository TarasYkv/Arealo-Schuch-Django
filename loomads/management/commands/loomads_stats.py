from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from loomads.models import Campaign, AdZone, Advertisement, AdImpression, AdClick

class Command(BaseCommand):
    help = 'Display LoomAds statistics and summary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics for each campaign and zone',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('📊 LoomAds System Statistics'))
        self.stdout.write('=' * 50)

        # Overall Statistics
        total_campaigns = Campaign.objects.count()
        active_campaigns = Campaign.objects.filter(status='active').count()
        total_zones = AdZone.objects.count()
        active_zones = AdZone.objects.filter(is_active=True).count()
        total_ads = Advertisement.objects.count()
        active_ads = Advertisement.objects.filter(is_active=True).count()
        
        self.stdout.write(f'📁 Campaigns: {total_campaigns} total, {active_campaigns} active')
        self.stdout.write(f'📍 Ad Zones: {total_zones} total, {active_zones} active')
        self.stdout.write(f'🎯 Advertisements: {total_ads} total, {active_ads} active')
        
        # Engagement Statistics
        total_impressions = AdImpression.objects.count()
        total_clicks = AdClick.objects.count()
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📈 Performance Metrics'))
        self.stdout.write(f'👁️  Total Impressions: {total_impressions:,}')
        self.stdout.write(f'🖱️  Total Clicks: {total_clicks:,}')
        self.stdout.write(f'📊 Overall CTR: {ctr:.2f}%')
        
        # Recent Activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_impressions = AdImpression.objects.filter(timestamp__gte=thirty_days_ago).count()
        recent_clicks = AdClick.objects.filter(timestamp__gte=thirty_days_ago).count()
        recent_ctr = (recent_clicks / recent_impressions * 100) if recent_impressions > 0 else 0
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📅 Last 30 Days'))
        self.stdout.write(f'👁️  Impressions: {recent_impressions:,}')
        self.stdout.write(f'🖱️  Clicks: {recent_clicks:,}')
        self.stdout.write(f'📊 CTR: {recent_ctr:.2f}%')
        
        if options['detailed']:
            self.show_detailed_stats()

    def show_detailed_stats(self):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📋 Detailed Statistics'))
        self.stdout.write('-' * 40)
        
        # Campaign Details
        campaigns = Campaign.objects.annotate(
            ads_count=Count('advertisements'),
            total_impressions=Sum('advertisements__impressions_count'),
            total_clicks=Sum('advertisements__clicks_count')
        )
        
        for campaign in campaigns:
            ctr = (campaign.total_clicks / campaign.total_impressions * 100) if campaign.total_impressions else 0
            status_icon = '🟢' if campaign.status == 'active' else '🟡' if campaign.status == 'paused' else '🔴'
            
            self.stdout.write(f'{status_icon} {campaign.name}:')
            self.stdout.write(f'    📊 {campaign.ads_count} ads, {campaign.total_impressions or 0:,} impressions, {campaign.total_clicks or 0:,} clicks')
            self.stdout.write(f'    📈 CTR: {ctr:.2f}%')
            self.stdout.write('')
        
        # Zone Performance
        self.stdout.write(self.style.SUCCESS('🎯 Zone Performance'))
        zones = AdZone.objects.annotate(
            ads_count=Count('advertisements')
        ).filter(is_active=True)
        
        for zone in zones:
            zone_impressions = AdImpression.objects.filter(zone=zone).count()
            zone_clicks = AdClick.objects.filter(zone=zone).count()
            zone_ctr = (zone_clicks / zone_impressions * 100) if zone_impressions else 0
            
            self.stdout.write(f'📍 {zone.name} ({zone.code}):')
            self.stdout.write(f'    📊 {zone.ads_count} ads, {zone_impressions:,} impressions, {zone_clicks:,} clicks')
            self.stdout.write(f'    📈 CTR: {zone_ctr:.2f}%')
            self.stdout.write('')
        
        # Top Performing Ads
        self.stdout.write(self.style.SUCCESS('🏆 Top Performing Ads'))
        top_ads = Advertisement.objects.filter(is_active=True).order_by('-clicks_count')[:5]
        
        for i, ad in enumerate(top_ads, 1):
            ctr = (ad.clicks_count / ad.impressions_count * 100) if ad.impressions_count else 0
            self.stdout.write(f'{i}. {ad.name}:')
            self.stdout.write(f'    📊 {ad.impressions_count:,} impressions, {ad.clicks_count:,} clicks, {ctr:.2f}% CTR')
            self.stdout.write(f'    🎯 Zones: {", ".join([z.code for z in ad.zones.all()])}')
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('✅ LoomAds system is operational!'))
#!/usr/bin/env python
"""
Setup script for LoomAds integration with LoomLine and FileShara
Creates all necessary ad zones and sample campaigns
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from loomads.models import AdZone, Campaign, Advertisement, LoomAdsSettings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def setup_loomads_zones():
    """Create all ad zones for LoomLine and FileShara integration"""

    # LoomLine Ad Zones
    loomline_zones = [
        {
            'code': 'loomline_header',
            'name': 'LoomLine Header Banner',
            'description': 'Top banner ad on LoomLine dashboard',
            'zone_type': 'header',
            'width': 728,
            'height': 90,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_content_cards',
            'name': 'LoomLine Content Cards',
            'description': 'Content cards between sections',
            'zone_type': 'content_card',
            'width': 350,
            'height': 200,
            'max_ads': 3,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_sidebar',
            'name': 'LoomLine Sidebar Main',
            'description': 'Main sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 250,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_sidebar_2',
            'name': 'LoomLine Sidebar Secondary',
            'description': 'Secondary sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 200,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_footer',
            'name': 'LoomLine Footer Banner',
            'description': 'Footer banner ad',
            'zone_type': 'footer',
            'width': 728,
            'height': 90,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_notification',
            'name': 'LoomLine Notification',
            'description': 'Notification style ad',
            'zone_type': 'notification',
            'width': 400,
            'height': 80,
            'app_restriction': 'loomline'
        },
        {
            'code': 'loomline_modal',
            'name': 'LoomLine Modal Ad',
            'description': 'Modal popup ad',
            'zone_type': 'modal',
            'width': 400,
            'height': 300,
            'app_restriction': 'loomline'
        },
    ]

    # FileShara Ad Zones
    fileshare_zones = [
        {
            'code': 'fileshare_top_banner',
            'name': 'FileShara Top Banner',
            'description': 'Very visible top banner',
            'zone_type': 'header',
            'width': 728,
            'height': 90,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_hero_ad',
            'name': 'FileShara Hero Ad',
            'description': 'Prominent hero section ad',
            'zone_type': 'header',
            'width': 600,
            'height': 120,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_content_cards',
            'name': 'FileShara Content Cards',
            'description': 'Multiple content cards',
            'zone_type': 'content_card',
            'width': 280,
            'height': 200,
            'max_ads': 4,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_sidebar_main',
            'name': 'FileShara Left Sidebar Main',
            'description': 'Main left sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 250,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_sidebar_secondary',
            'name': 'FileShara Left Sidebar Secondary',
            'description': 'Secondary left sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 200,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_sidebar_special',
            'name': 'FileShara Left Sidebar Special',
            'description': 'Special left sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 180,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_right_main',
            'name': 'FileShara Right Sidebar Main',
            'description': 'Main right sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 250,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_right_secondary',
            'name': 'FileShara Right Sidebar Secondary',
            'description': 'Secondary right sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 200,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_right_special',
            'name': 'FileShara Right Sidebar Special',
            'description': 'Special right sidebar ad',
            'zone_type': 'sidebar',
            'width': 300,
            'height': 180,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_form_bottom',
            'name': 'FileShara Form Bottom',
            'description': 'Ad below upload form',
            'zone_type': 'content_card',
            'width': 400,
            'height': 150,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_central_banner',
            'name': 'FileShara Central Banner',
            'description': 'Big central banner ad',
            'zone_type': 'header',
            'width': 728,
            'height': 120,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_feature_ads',
            'name': 'FileShara Feature Ads',
            'description': 'Ads between features',
            'zone_type': 'content_card',
            'width': 350,
            'height': 180,
            'max_ads': 3,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_post_features',
            'name': 'FileShara Post-Features',
            'description': 'Ad after features section',
            'zone_type': 'header',
            'width': 728,
            'height': 100,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_footer_banner',
            'name': 'FileShara Footer Banner',
            'description': 'Footer banner ad',
            'zone_type': 'footer',
            'width': 728,
            'height': 90,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_notification',
            'name': 'FileShara Notification',
            'description': 'Notification style ad',
            'zone_type': 'notification',
            'width': 500,
            'height': 80,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_modal',
            'name': 'FileShara Modal Ad',
            'description': 'Modal popup ad',
            'zone_type': 'modal',
            'width': 450,
            'height': 300,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_video_popup',
            'name': 'FileShara Video Popup',
            'description': 'Video popup ad',
            'zone_type': 'video_popup',
            'width': 320,
            'height': 180,
            'popup_delay': 8,
            'app_restriction': 'fileshare'
        },
        # Download page specific zones
        {
            'code': 'fileshare_download_top',
            'name': 'FileShara Download Top Banner',
            'description': 'Top banner on download page',
            'zone_type': 'header',
            'width': 728,
            'height': 90,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_download_hero',
            'name': 'FileShara Download Hero',
            'description': 'Hero ad on download page',
            'zone_type': 'header',
            'width': 600,
            'height': 150,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_download_middle',
            'name': 'FileShara Download Middle Cards',
            'description': 'Cards between download content',
            'zone_type': 'content_card',
            'width': 300,
            'height': 200,
            'max_ads': 3,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_download_footer',
            'name': 'FileShara Download Footer',
            'description': 'Footer ad on download page',
            'zone_type': 'footer',
            'width': 728,
            'height': 100,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_download_notification',
            'name': 'FileShara Download Notification',
            'description': 'Notification on download page',
            'zone_type': 'notification',
            'width': 500,
            'height': 80,
            'app_restriction': 'fileshare'
        },
        {
            'code': 'fileshare_download_modal',
            'name': 'FileShara Download Modal',
            'description': 'Modal on download page',
            'zone_type': 'modal',
            'width': 400,
            'height': 300,
            'app_restriction': 'fileshare'
        },
    ]

    all_zones = loomline_zones + fileshare_zones

    created_zones = []
    for zone_data in all_zones:
        zone, created = AdZone.objects.get_or_create(
            code=zone_data['code'],
            defaults=zone_data
        )
        if created:
            created_zones.append(zone.code)
            print(f"✓ Created zone: {zone.code} - {zone.name}")
        else:
            print(f"• Zone already exists: {zone.code}")

    return created_zones

def setup_sample_campaigns():
    """Create sample campaigns and advertisements"""

    # Get or create a superuser for campaigns
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='loomads_admin',
                email='admin@example.com',
                password='admin123'
            )
            print(f"✓ Created admin user: {admin_user.username}")
    except Exception as e:
        print(f"! Using existing admin user or error: {e}")
        admin_user = User.objects.filter(is_staff=True).first()

    if not admin_user:
        print("! No admin user available. Skipping campaign creation.")
        return

    # Sample campaigns
    campaigns_data = [
        {
            'name': 'LoomLine Premium Features',
            'description': 'Promote premium features of LoomLine',
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=90),
            'status': 'active',
            'ads': [
                {
                    'name': 'LoomLine Premium Banner',
                    'ad_type': 'html',
                    'title': 'Upgrade to LoomLine Pro',
                    'description': 'Get advanced project tracking features',
                    'html_content': '''
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center;">
                        <h3 style="margin: 0 0 10px 0; font-size: 18px;">🚀 LoomLine Pro</h3>
                        <p style="margin: 0 0 15px 0; font-size: 14px;">Advanced project tracking & team collaboration</p>
                        <button style="background: white; color: #667eea; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; cursor: pointer;">Upgrade Now</button>
                    </div>
                    ''',
                    'target_url': '#',
                    'zones': ['loomline_header', 'loomline_sidebar', 'loomline_footer']
                },
                {
                    'name': 'LoomLine Features Card',
                    'ad_type': 'html',
                    'title': 'Discover LoomLine Features',
                    'description': 'Content card for LoomLine features',
                    'html_content': '''
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 8px; text-align: center;">
                        <h4 style="margin: 0 0 8px 0; font-size: 16px;">📊 Smart Analytics</h4>
                        <p style="margin: 0 0 10px 0; font-size: 12px;">Track project progress with AI insights</p>
                        <small style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 3px;">Learn More</small>
                    </div>
                    ''',
                    'target_url': '#',
                    'zones': ['loomline_content_cards']
                }
            ]
        },
        {
            'name': 'FileShara Pro Storage',
            'description': 'Promote FileShara premium storage plans',
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=60),
            'status': 'active',
            'ads': [
                {
                    'name': 'FileShara Storage Hero',
                    'ad_type': 'html',
                    'title': 'Unlimited File Sharing',
                    'description': 'Hero banner for storage upgrade',
                    'html_content': '''
                    <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 25px; border-radius: 15px; text-align: center;">
                        <h2 style="margin: 0 0 10px 0; font-size: 24px;">💾 Unlimited Storage</h2>
                        <p style="margin: 0 0 15px 0; font-size: 16px;">Share files up to 10GB • Keep for 1 year • Premium support</p>
                        <button style="background: white; color: #ff6b6b; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer;">Get Premium</button>
                    </div>
                    ''',
                    'target_url': '#',
                    'zones': ['fileshare_hero_ad', 'fileshare_central_banner', 'fileshare_download_hero']
                },
                {
                    'name': 'FileShara Sidebar Pro',
                    'ad_type': 'html',
                    'title': 'FileShara Pro Benefits',
                    'description': 'Sidebar promotion',
                    'html_content': '''
                    <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                        <h3 style="margin: 0 0 10px 0; font-size: 18px;">⚡ Go Pro</h3>
                        <ul style="margin: 0 0 15px 0; padding: 0; list-style: none; font-size: 14px; text-align: left;">
                            <li style="margin: 5px 0;">✓ 10GB file size</li>
                            <li style="margin: 5px 0;">✓ 1 year storage</li>
                            <li style="margin: 5px 0;">✓ Password protection</li>
                            <li style="margin: 5px 0;">✓ Download tracking</li>
                        </ul>
                        <button style="background: white; color: #4facfe; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer;">Upgrade</button>
                    </div>
                    ''',
                    'target_url': '#',
                    'zones': ['fileshare_sidebar_main', 'fileshare_right_main']
                },
                {
                    'name': 'FileShara Feature Cards',
                    'ad_type': 'html',
                    'title': 'Advanced Features',
                    'description': 'Feature promotion cards',
                    'html_content': '''
                    <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #fff;">
                        <h4 style="margin: 0 0 8px 0; font-size: 16px; color: #2c3e50;">🔒 Security+</h4>
                        <p style="margin: 0 0 10px 0; font-size: 12px;">Advanced encryption & access controls</p>
                        <small style="background: #2c3e50; color: white; padding: 4px 8px; border-radius: 4px;">Try Free</small>
                    </div>
                    ''',
                    'target_url': '#',
                    'zones': ['fileshare_content_cards', 'fileshare_feature_ads', 'fileshare_download_middle']
                }
            ]
        }
    ]

    for campaign_data in campaigns_data:
        ads_data = campaign_data.pop('ads')

        campaign, created = Campaign.objects.get_or_create(
            name=campaign_data['name'],
            defaults={
                **campaign_data,
                'created_by': admin_user
            }
        )

        if created:
            print(f"✓ Created campaign: {campaign.name}")

            # Create ads for this campaign
            for ad_data in ads_data:
                zones_codes = ad_data.pop('zones')

                ad = Advertisement.objects.create(
                    campaign=campaign,
                    **ad_data
                )

                # Assign zones
                for zone_code in zones_codes:
                    try:
                        zone = AdZone.objects.get(code=zone_code)
                        ad.zones.add(zone)
                    except AdZone.DoesNotExist:
                        print(f"! Zone not found: {zone_code}")

                print(f"  ✓ Created ad: {ad.name} with {len(zones_codes)} zones")
        else:
            print(f"• Campaign already exists: {campaign.name}")

def setup_loomads_settings():
    """Configure LoomAds settings for app integration"""

    settings = LoomAdsSettings.get_settings()

    # Enable zones for both apps
    settings.set_zone_enabled('header', 'loomline', True)
    settings.set_zone_enabled('footer', 'loomline', True)
    settings.set_zone_enabled('sidebar', 'loomline', True)
    settings.set_zone_enabled('content_card', 'loomline', True)
    settings.set_zone_enabled('notification', 'loomline', True)
    settings.set_zone_enabled('modal', 'loomline', True)

    settings.set_zone_enabled('header', 'fileshare', True)
    settings.set_zone_enabled('footer', 'fileshare', True)
    settings.set_zone_enabled('sidebar', 'fileshare', True)
    settings.set_zone_enabled('content_card', 'fileshare', True)
    settings.set_zone_enabled('notification', 'fileshare', True)
    settings.set_zone_enabled('modal', 'fileshare', True)
    settings.set_zone_enabled('video_popup', 'fileshare', True)

    print("✓ LoomAds settings configured for LoomLine and FileShara")

def main():
    """Main setup function"""

    print("🚀 Setting up LoomAds integration for LoomLine and FileShara")
    print("=" * 60)

    # Setup zones
    print("\n📍 Creating Ad Zones...")
    created_zones = setup_loomads_zones()
    print(f"Created {len(created_zones)} new zones")

    # Setup settings
    print("\n⚙️  Configuring LoomAds Settings...")
    setup_loomads_settings()

    # Setup sample campaigns
    print("\n📢 Creating Sample Campaigns...")
    setup_sample_campaigns()

    print("\n" + "=" * 60)
    print("✅ LoomAds integration setup complete!")
    print("\nNext steps:")
    print("1. Visit Django Admin to manage campaigns and ads")
    print("2. Create real advertising content")
    print("3. Test the integration on both LoomLine and FileShara")
    print("4. Monitor ad performance and adjust as needed")
    print("\nZone summary:")
    print(f"• LoomLine: 7 ad zones (header, sidebar, content cards, footer, notification, modal)")
    print(f"• FileShara: 21 ad zones (very visible placement throughout the app)")
    print(f"• Total zones created: {AdZone.objects.count()}")
    print(f"• Total campaigns: {Campaign.objects.count()}")
    print(f"• Total advertisements: {Advertisement.objects.count()}")

if __name__ == "__main__":
    main()
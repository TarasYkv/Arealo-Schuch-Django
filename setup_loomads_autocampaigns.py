#!/usr/bin/env python
"""
Setup Auto-Kampagnen für LoomAds Integration
Nutzt die intelligente AutoCampaign und AutoCampaignFormat Funktionalität
"""

import os
import sys
import django
import json

# Setup Django
sys.path.insert(0, '/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from loomads.models import (
    AdZone, Campaign, Advertisement, LoomAdsSettings,
    AutoCampaignFormat, AutoCampaign, AutoAdvertisement
)
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def create_auto_campaign_formats():
    """Erstellt Auto-Kampagnen Formate für verschiedene Zone-Typen"""

    formats_data = [
        {
            'name': 'LoomLine Dashboard Format',
            'format_type': 'banner_728x90',
            'description': 'Optimiert für LoomLine Dashboard Header und Footer',
            'target_zone_types': ['header', 'footer'],
            'target_dimensions': ['728x90'],
            'grouping_strategy': 'by_type_and_dimensions',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 10
        },
        {
            'name': 'LoomLine Sidebar Format',
            'format_type': 'sidebar_300x250',
            'description': 'Sidebar-Anzeigen für LoomLine',
            'target_zone_types': ['sidebar'],
            'target_dimensions': ['300x250', '300x200'],
            'grouping_strategy': 'by_dimensions',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 8
        },
        {
            'name': 'LoomLine Content Cards',
            'format_type': 'content_card_350x200',
            'description': 'Content Cards für LoomLine Feed',
            'target_zone_types': ['content_card'],
            'target_dimensions': ['350x200'],
            'grouping_strategy': 'by_type',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 9
        },
        {
            'name': 'FileShara Universal Sidebar',
            'format_type': 'sidebar_300x250',
            'description': 'Universelle Sidebar-Anzeigen für FileShara (links und rechts)',
            'target_zone_types': ['sidebar'],
            'target_dimensions': ['300x250', '300x200', '300x180'],
            'grouping_strategy': 'by_dimensions',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 9
        },
        {
            'name': 'FileShara Hero Banners',
            'format_type': 'custom',
            'description': 'Große Hero-Banner für FileShara',
            'target_zone_types': ['header'],
            'target_dimensions': ['600x120', '600x150', '728x120', '728x100'],
            'grouping_strategy': 'by_dimensions',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 10
        },
        {
            'name': 'FileShara Content Grid',
            'format_type': 'custom',
            'description': 'Content-Grid für FileShara Feature-Bereiche',
            'target_zone_types': ['content_card'],
            'target_dimensions': ['280x200', '300x200', '350x180', '350x200'],
            'grouping_strategy': 'by_type_and_dimensions',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 8
        },
        {
            'name': 'Cross-App Modal Format',
            'format_type': 'modal_400x300',
            'description': 'Modal-Popups für beide Apps',
            'target_zone_types': ['modal'],
            'target_dimensions': ['400x300', '450x300'],
            'grouping_strategy': 'by_type',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 7
        },
        {
            'name': 'Cross-App Notification',
            'format_type': 'notification_300x80',
            'description': 'Benachrichtigungs-Banner für beide Apps',
            'target_zone_types': ['notification'],
            'target_dimensions': ['400x80', '500x80'],
            'grouping_strategy': 'by_type',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 6
        },
        {
            'name': 'FileShara Video Overlay',
            'format_type': 'video_overlay_300x100',
            'description': 'Video-Overlay speziell für FileShara',
            'target_zone_types': ['video_popup'],
            'target_dimensions': ['320x180'],
            'grouping_strategy': 'by_type',
            'auto_assign_similar_zones': True,
            'excluded_zones': [],
            'priority': 5
        }
    ]

    created_formats = []
    for format_data in formats_data:
        format_obj, created = AutoCampaignFormat.objects.get_or_create(
            name=format_data['name'],
            defaults=format_data
        )
        if created:
            print(f"✓ Created format: {format_obj.name} (Matches {format_obj.get_zone_count()} zones)")
            created_formats.append(format_obj)
        else:
            print(f"• Format already exists: {format_obj.name}")

    return created_formats

def create_auto_campaigns():
    """Erstellt Auto-Kampagnen mit automatischer Optimierung"""

    # Get or create admin user
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.filter(is_staff=True).first()

    if not admin_user:
        print("! No admin user available. Skipping auto-campaign creation.")
        return

    campaigns_data = [
        {
            'name': 'LoomLine Premium Auto-Campaign',
            'description': 'Automatische Kampagne für LoomLine Premium Features mit KI-Optimierung',
            'format_name': 'LoomLine Dashboard Format',
            'content_strategy': 'format_optimized',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': True,
            'performance_threshold_ctr': 0.3,
            'daily_impression_limit': 10000,
            'total_impression_limit': 100000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=90),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'LoomLine Premium - Automatisch optimiert',
                'description': 'KI-optimierte Anzeige für maximale Performance',
                'target_url': '#upgrade-premium',
                'target_type': '_blank',
                'weight': 7,
                'html_content': '''
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 25px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <h3 style="margin: 0 0 5px 0; font-size: 16px;">🚀 LoomLine Premium - KI-Optimiert</h3>
                        <p style="margin: 0; font-size: 13px; opacity: 0.9;">Automatisch angepasste Werbung für beste Conversion</p>
                    </div>
                    <button style="background: white; color: #667eea; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; cursor: pointer; white-space: nowrap;">Jetzt upgraden</button>
                </div>
                '''
            }
        },
        {
            'name': 'LoomLine Sidebar Auto-Campaign',
            'description': 'Intelligente Sidebar-Kampagne mit A/B Testing',
            'format_name': 'LoomLine Sidebar Format',
            'content_strategy': 'a_b_testing',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': False,
            'performance_threshold_ctr': 0.5,
            'daily_impression_limit': 5000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=60),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'Smart Sidebar Ad',
                'description': 'A/B getestete Sidebar-Anzeige',
                'target_url': '#features',
                'target_type': '_blank',
                'weight': 6,
                'html_content': '''
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 12px; padding: 20px; color: white; text-align: center;">
                    <h4 style="margin: 0 0 10px 0; font-size: 18px;">📈 Performance Boost</h4>
                    <p style="margin: 0 0 15px 0; font-size: 14px;">KI-gestützte Projektanalyse</p>
                    <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 8px;">
                        <strong style="font-size: 24px;">+45%</strong>
                        <br><small>Produktivität</small>
                    </div>
                    <button style="background: white; color: #f5576c; border: none; padding: 10px 20px; margin-top: 15px; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%;">Mehr erfahren</button>
                </div>
                '''
            }
        },
        {
            'name': 'FileShara Mega Auto-Campaign',
            'description': 'Mega-Kampagne für alle FileShara Zonen mit intelligenter Verteilung',
            'format_name': 'FileShara Universal Sidebar',
            'content_strategy': 'zone_specific',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': True,
            'performance_threshold_ctr': 0.4,
            'daily_impression_limit': 20000,
            'total_impression_limit': 500000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=120),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'FileShara Pro - Zone-optimiert',
                'description': 'Zonenspezifisch angepasste Werbung',
                'target_url': '#pro-upgrade',
                'target_type': '_blank',
                'weight': 9,
                'html_content': '''
                <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); border-radius: 15px; padding: 25px; color: white; text-align: center; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -20px; right: -20px; width: 80px; height: 80px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                    <h3 style="margin: 0 0 10px 0; font-size: 20px; position: relative; z-index: 1;">💾 FileShara PRO</h3>
                    <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px; margin: 15px 0;">
                        <div style="font-size: 28px; font-weight: bold; margin-bottom: 5px;">100GB</div>
                        <div style="font-size: 14px; opacity: 0.9;">Cloud-Speicher</div>
                    </div>
                    <ul style="list-style: none; padding: 0; margin: 15px 0; text-align: left; font-size: 14px;">
                        <li style="margin: 8px 0;">✓ Unbegrenzte Übertragungen</li>
                        <li style="margin: 8px 0;">✓ Premium Support 24/7</li>
                        <li style="margin: 8px 0;">✓ Erweiterte Sicherheit</li>
                    </ul>
                    <button style="background: white; color: #ff6b6b; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; width: 100%; transition: all 0.3s;">
                        Jetzt upgraden - 50% Rabatt
                    </button>
                </div>
                '''
            }
        },
        {
            'name': 'FileShara Hero Auto-Campaign',
            'description': 'Hero-Banner Kampagne mit automatischer Größenanpassung',
            'format_name': 'FileShara Hero Banners',
            'content_strategy': 'format_optimized',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': False,
            'performance_threshold_ctr': 0.6,
            'daily_impression_limit': 15000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=45),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'Hero Banner - Adaptiv',
                'description': 'Automatisch angepasster Hero-Banner',
                'target_url': '#special-offer',
                'target_type': '_blank',
                'weight': 8,
                'html_content': '''
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 20px; padding: 30px; color: white; text-align: center; box-shadow: 0 20px 60px rgba(79, 172, 254, 0.4);">
                    <h2 style="margin: 0 0 10px 0; font-size: 28px; text-shadow: 0 2px 10px rgba(0,0,0,0.1);">⚡ Flash Sale - Nur heute!</h2>
                    <p style="margin: 0 0 20px 0; font-size: 18px; opacity: 0.95;">FileShara Premium lebenslang zum halben Preis</p>
                    <div style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
                        <div style="background: rgba(255,255,255,0.2); padding: 15px 25px; border-radius: 10px;">
                            <div style="font-size: 24px; font-weight: bold;">€49</div>
                            <del style="opacity: 0.7;">€99</del>
                        </div>
                        <div style="background: rgba(255,255,255,0.2); padding: 15px 25px; border-radius: 10px;">
                            <div style="font-size: 24px; font-weight: bold;">∞</div>
                            <div style="font-size: 12px;">Lebenslang</div>
                        </div>
                    </div>
                    <button style="background: white; color: #4facfe; border: none; padding: 15px 40px; margin-top: 20px; border-radius: 10px; font-weight: bold; font-size: 18px; cursor: pointer; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                        Jetzt sichern →
                    </button>
                </div>
                '''
            }
        },
        {
            'name': 'Cross-App Content Cards Campaign',
            'description': 'Content Cards für beide Apps mit KI-Optimierung',
            'format_name': 'LoomLine Content Cards',
            'content_strategy': 'format_optimized',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': True,
            'performance_threshold_ctr': 0.5,
            'daily_impression_limit': 8000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=60),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'Smart Content Card',
                'description': 'KI-optimierte Content Card',
                'target_url': '#learn-more',
                'target_type': '_blank',
                'weight': 7,
                'html_content': '''
                <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); border-radius: 12px; padding: 20px; text-align: center; border: 2px solid rgba(255,255,255,0.5);">
                    <div style="font-size: 40px; margin-bottom: 10px;">🎯</div>
                    <h4 style="margin: 0 0 10px 0; color: #2c3e50; font-size: 18px;">Smart Targeting</h4>
                    <p style="margin: 0 0 15px 0; color: #555; font-size: 14px;">KI-basierte Zielgruppenanalyse für bessere Ergebnisse</p>
                    <button style="background: #2c3e50; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer;">Entdecken</button>
                </div>
                '''
            }
        },
        {
            'name': 'Modal & Notification Auto-Campaign',
            'description': 'Intelligente Modal- und Benachrichtigungs-Kampagne',
            'format_name': 'Cross-App Modal Format',
            'content_strategy': 'a_b_testing',
            'auto_optimize_performance': True,
            'auto_pause_low_performers': False,
            'performance_threshold_ctr': 0.8,
            'daily_impression_limit': 3000,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=30),
            'status': 'active',
            'base_creative': {
                'type': 'html',
                'title': 'Smart Modal',
                'description': 'Intelligentes Modal mit A/B Testing',
                'target_url': '#special-modal-offer',
                'target_type': '_blank',
                'weight': 5,
                'html_content': '''
                <div style="background: white; border-radius: 20px; padding: 30px; text-align: center; box-shadow: 0 25px 70px rgba(0,0,0,0.2);">
                    <div style="font-size: 60px; margin-bottom: 20px;">🎁</div>
                    <h3 style="margin: 0 0 15px 0; color: #333; font-size: 24px;">Exklusives Angebot!</h3>
                    <p style="margin: 0 0 20px 0; color: #666; font-size: 16px;">Nur für ausgewählte Nutzer - Sparen Sie 70%</p>
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin: 20px 0;">
                        <div style="font-size: 32px; font-weight: bold;">70% RABATT</div>
                        <div style="font-size: 14px; opacity: 0.9;">Gültig für die nächsten 24 Stunden</div>
                    </div>
                    <button style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 15px 40px; border-radius: 10px; font-weight: bold; font-size: 18px; cursor: pointer; width: 100%;">
                        Angebot sichern
                    </button>
                    <p style="margin: 15px 0 0 0; color: #999; font-size: 12px;">Kein Risiko - 30 Tage Geld-zurück-Garantie</p>
                </div>
                '''
            }
        }
    ]

    created_campaigns = []
    for campaign_data in campaigns_data:
        format_name = campaign_data.pop('format_name')
        base_creative = campaign_data.pop('base_creative')

        # Find the format
        try:
            target_format = AutoCampaignFormat.objects.get(name=format_name)
        except AutoCampaignFormat.DoesNotExist:
            print(f"! Format not found: {format_name}")
            continue

        # Create the auto-campaign
        auto_campaign, created = AutoCampaign.objects.get_or_create(
            name=campaign_data['name'],
            defaults={
                **campaign_data,
                'target_format': target_format,
                'created_by': admin_user
            }
        )

        if created:
            print(f"✓ Created auto-campaign: {auto_campaign.name}")

            # Create a base campaign for the auto-generated ads
            base_campaign = Campaign.objects.create(
                name=f"{auto_campaign.name} - Base",
                description=f"Base campaign for auto-generated ads from {auto_campaign.name}",
                created_by=admin_user,
                status='active',
                start_date=auto_campaign.start_date,
                end_date=auto_campaign.end_date,
                daily_impression_limit=auto_campaign.daily_impression_limit,
                total_impression_limit=auto_campaign.total_impression_limit
            )
            print(f"  ✓ Created base campaign for auto-ads")

            # Create auto-advertisements for each matching zone
            target_zones = auto_campaign.get_target_zones()
            print(f"  → Found {target_zones.count()} matching zones")

            for zone in target_zones[:10]:  # Limit to 10 zones for demo
                # Create AutoAdvertisement
                auto_ad = AutoAdvertisement.objects.create(
                    auto_campaign=auto_campaign,
                    base_creative=json.dumps(base_creative),
                    target_zone=zone,
                    name=f"{auto_campaign.name} - {zone.code}",
                    generation_strategy='format_optimized',
                    is_active=True
                )

                # Create the actual Advertisement with the base campaign
                advertisement = Advertisement.objects.create(
                    campaign=base_campaign,
                    name=auto_ad.name,
                    ad_type=base_creative.get('type', 'html'),
                    title=base_creative.get('title', ''),
                    description=base_creative.get('description', ''),
                    html_content=base_creative.get('html_content', ''),
                    target_url=base_creative.get('target_url', '#'),
                    target_type=base_creative.get('target_type', '_blank'),
                    weight=base_creative.get('weight', 5),
                    is_active=True
                )

                # Assign zone to the advertisement
                advertisement.zones.add(zone)

                # Link the advertisement to the auto_ad
                auto_ad.advertisement = advertisement
                auto_ad.save()

                print(f"    ✓ Created auto-ad for zone: {zone.code}")

            # Don't update performance score yet (no impressions yet)
            # auto_campaign.update_performance_score()
            created_campaigns.append(auto_campaign)
        else:
            print(f"• Auto-campaign already exists: {auto_campaign.name}")

    return created_campaigns

def optimize_existing_campaigns():
    """Optimiert bestehende Auto-Kampagnen"""

    print("\n🔧 Optimizing existing auto-campaigns...")

    active_campaigns = AutoCampaign.objects.filter(status='active')

    for campaign in active_campaigns:
        if campaign.auto_optimize_performance:
            # Skip optimization for now (no impressions yet)
            print(f"  • Skipping optimization for {campaign.name} (no impressions yet)")

def display_statistics():
    """Zeigt Statistiken über Auto-Kampagnen"""

    print("\n📊 Auto-Campaign Statistics:")
    print("=" * 60)

    formats = AutoCampaignFormat.objects.all()
    print(f"Total Formats: {formats.count()}")
    for format_obj in formats:
        zones = format_obj.get_matching_zones()
        print(f"  • {format_obj.name}: {zones.count()} zones")

    print(f"\nTotal Auto-Campaigns: {AutoCampaign.objects.count()}")
    print(f"Active Auto-Campaigns: {AutoCampaign.objects.filter(status='active').count()}")
    print(f"Total Auto-Advertisements: {AutoAdvertisement.objects.count()}")
    print(f"Active Auto-Advertisements: {AutoAdvertisement.objects.filter(is_active=True).count()}")

    # Performance overview
    campaigns = AutoCampaign.objects.filter(status='active')
    if campaigns:
        avg_score = sum(c.performance_score for c in campaigns) / campaigns.count()
        print(f"\nAverage Performance Score: {avg_score:.2f}/100")

    # Zone coverage
    total_zones = AdZone.objects.filter(is_active=True).count()
    covered_zones = AutoAdvertisement.objects.filter(is_active=True).values('target_zone').distinct().count()
    coverage = (covered_zones / total_zones * 100) if total_zones > 0 else 0
    print(f"Zone Coverage: {covered_zones}/{total_zones} ({coverage:.1f}%)")

def main():
    """Main setup function for auto-campaigns"""

    print("🤖 Setting up LoomAds Auto-Campaigns for LoomLine and FileShara")
    print("=" * 60)

    # Create formats
    print("\n📐 Creating Auto-Campaign Formats...")
    formats = create_auto_campaign_formats()
    print(f"Created {len(formats)} new formats")

    # Create auto-campaigns
    print("\n🚀 Creating Auto-Campaigns...")
    campaigns = create_auto_campaigns()
    print(f"Created {len(campaigns)} new auto-campaigns")

    # Optimize campaigns
    optimize_existing_campaigns()

    # Display statistics
    display_statistics()

    print("\n" + "=" * 60)
    print("✅ Auto-Campaign setup complete!")
    print("\nKey Features Enabled:")
    print("• Automatic zone matching based on dimensions and types")
    print("• Performance-based optimization with CTR thresholds")
    print("• A/B testing capabilities for better conversion")
    print("• Zone-specific content adaptation")
    print("• Automatic pausing of low-performing ads")
    print("• Real-time performance scoring")
    print("\nNext Steps:")
    print("1. Monitor performance scores in Django Admin")
    print("2. Review auto-generated advertisements")
    print("3. Adjust CTR thresholds based on actual performance")
    print("4. Create additional formats for new zone combinations")

if __name__ == "__main__":
    main()
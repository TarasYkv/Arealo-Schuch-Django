#!/usr/bin/env python
"""
Setup-Script für App-Kampagnen Test
Erstellt Beispiel App-Kampagnen für alle verfügbaren Apps
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, '/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth import get_user_model
from loomads.models import AppCampaign, AppAdvertisement
from django.utils import timezone

User = get_user_model()

def setup_app_campaigns():
    """Erstellt Test-App-Kampagnen für alle Apps"""
    print("🚀 Setting up App-Kampagnen...")
    print("=" * 50)

    # Get or create admin user
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}
    )
    if created:
        admin_user.set_password('admin')
        admin_user.save()

    # App Campaign definitions
    app_campaigns_data = [
        {
            'app': 'loomline',
            'campaigns': [
                {
                    'name': 'LoomLine Premium Features',
                    'description': 'Bewirbt Premium-Features von LoomLine wie erweiterte Projektmanagement-Tools',
                    'priority': 4,
                    'weight_multiplier': 1.5,
                    'ads': [
                        {
                            'name': 'Premium Dashboard',
                            'title': 'LoomLine Premium Dashboard',
                            'description_text': 'Erweiterte Projektübersicht mit KI-powered Insights',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        color: white; padding: 20px; border-radius: 10px;
                                        text-align: center; font-family: Arial, sans-serif;">
                                <h3 style="margin: 0 0 10px 0;">📊 LoomLine Premium</h3>
                                <p style="margin: 0 0 15px 0; font-size: 14px;">
                                    Erweiterte Dashboard-Features mit KI-Unterstützung
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 8px 16px;
                                           border-radius: 5px; display: inline-block; font-weight: bold;">
                                    Jetzt upgraden →
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://loomline.app/premium'
                        },
                        {
                            'name': 'Team Collaboration',
                            'title': 'LoomLine Team Features',
                            'description_text': 'Verbesserte Team-Zusammenarbeit und Kommunikation',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                        color: white; padding: 15px; border-radius: 8px;
                                        font-family: Arial, sans-serif;">
                                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                    <span style="font-size: 20px; margin-right: 10px;">👥</span>
                                    <strong>Team Collaboration</strong>
                                </div>
                                <p style="margin: 0 0 12px 0; font-size: 12px;">
                                    Echtzeit-Kommunikation und gemeinsame Projektbearbeitung
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 6px 12px;
                                           border-radius: 4px; font-size: 11px; text-align: center;">
                                    Team beitreten
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://loomline.app/teams'
                        }
                    ]
                }
            ]
        },
        {
            'app': 'fileshare',
            'campaigns': [
                {
                    'name': 'FileShara Pro Storage',
                    'description': 'Bewirbt erweiterte Speicheroptionen und Premium-Features',
                    'priority': 5,
                    'weight_multiplier': 2.0,
                    'ads': [
                        {
                            'name': 'Unlimited Storage',
                            'title': 'FileShara Unlimited',
                            'description_text': 'Unbegrenzter Speicherplatz für alle deine Dateien',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                                        color: white; padding: 18px; border-radius: 12px;
                                        text-align: center; font-family: Arial, sans-serif;">
                                <h3 style="margin: 0 0 8px 0;">💾 Unlimited Storage</h3>
                                <p style="margin: 0 0 12px 0; font-size: 13px;">
                                    Nie wieder Speicherplatz-Sorgen mit FileShara Pro
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 8px 16px;
                                           border-radius: 6px; display: inline-block; font-weight: bold;">
                                    Jetzt upgraden
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://fileshare.app/upgrade'
                        }
                    ]
                }
            ]
        },
        {
            'app': 'streamrec',
            'campaigns': [
                {
                    'name': 'StreamRec Studio Equipment',
                    'description': 'Bewirbt professionelle Streaming und Recording Equipment',
                    'priority': 3,
                    'weight_multiplier': 1.2,
                    'ads': [
                        {
                            'name': 'Professional Recording',
                            'title': 'StreamRec Pro Studio',
                            'description_text': 'Professionelle Recording-Ausrüstung für Content Creator',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
                                        color: white; padding: 16px; border-radius: 10px;
                                        font-family: Arial, sans-serif;">
                                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                                    <span style="font-size: 18px; margin-right: 8px;">🎬</span>
                                    <strong>StreamRec Studio</strong>
                                </div>
                                <p style="margin: 0 0 10px 0; font-size: 12px;">
                                    Professional Recording & Streaming Equipment
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 6px 12px;
                                           border-radius: 4px; font-size: 11px; text-align: center;">
                                    Equipment ansehen →
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://streamrec.app/equipment'
                        }
                    ]
                }
            ]
        },
        {
            'app': 'promptpro',
            'campaigns': [
                {
                    'name': 'PromptPro AI Premium',
                    'description': 'Bewirbt erweiterte KI-Prompt-Features und Templates',
                    'priority': 4,
                    'weight_multiplier': 1.8,
                    'ads': [
                        {
                            'name': 'AI Prompt Optimizer',
                            'title': 'PromptPro AI Optimizer',
                            'description_text': 'KI-gestützte Prompt-Optimierung für bessere Ergebnisse',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
                                        color: white; padding: 18px; border-radius: 10px;
                                        text-align: center; font-family: Arial, sans-serif;">
                                <h3 style="margin: 0 0 8px 0;">🤖 AI Optimizer</h3>
                                <p style="margin: 0 0 12px 0; font-size: 13px;">
                                    Intelligente Prompt-Optimierung mit KI-Power
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 8px 16px;
                                           border-radius: 6px; display: inline-block; font-weight: bold;">
                                    Jetzt optimieren ✨
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://promptpro.app/optimizer'
                        }
                    ]
                }
            ]
        },
        {
            'app': 'blog',
            'campaigns': [
                {
                    'name': 'Blog SEO Tools',
                    'description': 'Bewirbt SEO-Tools und Content-Marketing Features',
                    'priority': 3,
                    'weight_multiplier': 1.3,
                    'ads': [
                        {
                            'name': 'SEO Content Optimizer',
                            'title': 'Blog SEO Optimizer',
                            'description_text': 'Optimiere deine Blog-Artikel für bessere Rankings',
                            'html_content': '''
                            <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                                        color: white; padding: 15px; border-radius: 8px;
                                        font-family: Arial, sans-serif;">
                                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                                    <span style="font-size: 16px; margin-right: 8px;">📝</span>
                                    <strong>SEO Optimizer</strong>
                                </div>
                                <p style="margin: 0 0 10px 0; font-size: 11px;">
                                    Bessere Rankings durch optimierte Blog-Inhalte
                                </p>
                                <div style="background: rgba(255,255,255,0.2); padding: 5px 10px;
                                           border-radius: 4px; font-size: 10px; text-align: center;">
                                    Jetzt optimieren
                                </div>
                            </div>
                            ''',
                            'link_url': 'https://blog.app/seo'
                        }
                    ]
                }
            ]
        }
    ]

    created_campaigns = 0
    created_ads = 0

    for app_data in app_campaigns_data:
        app_name = app_data['app']
        print(f"\n📱 Setting up campaigns for {app_name.upper()}...")

        for campaign_data in app_data['campaigns']:
            # Create App Campaign
            start_date = timezone.now()
            end_date = start_date + timedelta(days=90)

            app_campaign, created = AppCampaign.objects.get_or_create(
                name=campaign_data['name'],
                app_target=app_name,
                defaults={
                    'description': campaign_data['description'],
                    'created_by': admin_user,
                    'status': 'active',
                    'priority': campaign_data['priority'],
                    'start_date': start_date,
                    'end_date': end_date,
                    'weight_multiplier': campaign_data['weight_multiplier'],
                    'auto_include_new_zones': True,
                    'daily_impression_limit': 1000,
                    'total_impression_limit': 50000
                }
            )

            if created:
                created_campaigns += 1
                print(f"  ✅ Created campaign: {campaign_data['name']}")

                # Create App Advertisements
                for ad_data in campaign_data['ads']:
                    app_ad = AppAdvertisement.objects.create(
                        app_campaign=app_campaign,
                        name=ad_data['name'],
                        description=f"App-Anzeige für {app_name}",
                        ad_type='html',
                        title=ad_data['title'],
                        description_text=ad_data['description_text'],
                        html_content=ad_data['html_content'],
                        link_url=ad_data['link_url'],
                        weight=8,
                        is_active=True
                    )
                    created_ads += 1
                    print(f"    🎯 Created ad: {ad_data['name']}")

                    # Sync with app zones
                    app_ad.sync_with_app_zones()
                    print(f"    🔄 Synced with {app_ad.zones.count()} zones")

            else:
                print(f"  ⚠️  Campaign already exists: {campaign_data['name']}")

    print(f"\n✅ Setup completed!")
    print(f"📊 Created {created_campaigns} new app campaigns")
    print(f"🎯 Created {created_ads} new app advertisements")

    # Summary
    total_campaigns = AppCampaign.objects.count()
    total_ads = AppAdvertisement.objects.count()
    print(f"\n📈 Total App Campaigns: {total_campaigns}")
    print(f"📈 Total App Advertisements: {total_ads}")

    return True

def test_app_campaigns():
    """Teste die App-Kampagnen Funktionalität"""
    print("\n🧪 Testing App-Kampagnen functionality...")
    print("=" * 50)

    for app_target in ['loomline', 'fileshare', 'streamrec', 'promptpro', 'blog']:
        campaigns = AppCampaign.objects.filter(app_target=app_target)
        print(f"\n📱 {app_target.upper()}:")

        for campaign in campaigns:
            target_zones = campaign.get_target_zones()
            ads = campaign.app_advertisements.all()
            print(f"  📋 {campaign.name}")
            print(f"    🎯 Target zones: {len(target_zones)}")
            print(f"    📢 Advertisements: {ads.count()}")

            for ad in ads:
                print(f"      • {ad.name} (Weight: {ad.effective_weight})")

def main():
    """Hauptfunktion"""
    try:
        setup_app_campaigns()
        test_app_campaigns()

        print("\n🎉 App-Kampagnen Setup erfolgreich!")
        print("\nNext Steps:")
        print("1. Admin Interface: http://127.0.0.1:8000/admin/loomads/appcampaign/")
        print("2. App Advertisements: http://127.0.0.1:8000/admin/loomads/appadvertisement/")
        print("3. Test the campaigns by visiting the respective app pages")
        print("4. Monitor performance and adjust weights as needed")

    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
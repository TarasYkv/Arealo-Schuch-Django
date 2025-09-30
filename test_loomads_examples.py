#!/usr/bin/env python
"""
Test-Script für die erweiterte LoomAds Examples-Seite
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from loomads.models import AdZone
from loomads.views_frontend import (
    get_app_display_name,
    determine_app_from_zone_code,
    get_sample_ads_for_zone,
    get_size_category
)

def test_examples_integration():
    """Teste die Examples-Integration"""
    print("🧪 Testing LoomAds Examples Integration")
    print("=" * 50)

    # Test App-Name Zuordnung
    print("\n📱 Testing App Name Mapping:")
    test_codes = ['loomline_header', 'fileshare_sidebar', 'videos_modal', 'dashboard_banner']
    for code in test_codes:
        app = determine_app_from_zone_code(code)
        display_name = get_app_display_name(app)
        print(f"  {code} -> {app} -> {display_name}")

    # Test Größenkategorien
    print("\n📏 Testing Size Categories:")
    test_sizes = [(300, 80), (400, 200), (728, 90), (600, 400)]
    for width, height in test_sizes:
        category = get_size_category(width, height)
        print(f"  {width}x{height}px -> {category}")

    # Test Zonen aus der Datenbank
    print("\n🎯 Testing Database Zones:")
    loomline_zones = AdZone.objects.filter(code__startswith='loomline_', is_active=True)[:3]
    fileshare_zones = AdZone.objects.filter(code__startswith='fileshare_', is_active=True)[:3]

    print(f"\nLoomLine Zones ({loomline_zones.count()}):")
    for zone in loomline_zones:
        sample_ads = get_sample_ads_for_zone(zone, 'loomline')
        print(f"  {zone.code}: {zone.name} ({zone.width}x{zone.height}) - {len(sample_ads)} ads")

    print(f"\nFileShara Zones ({fileshare_zones.count()}):")
    for zone in fileshare_zones:
        sample_ads = get_sample_ads_for_zone(zone, 'fileshare')
        print(f"  {zone.code}: {zone.name} ({zone.width}x{zone.height}) - {len(sample_ads)} ads")

    # Gesamtstatistik
    all_zones = AdZone.objects.filter(is_active=True)
    loomline_count = all_zones.filter(code__startswith='loomline_').count()
    fileshare_count = all_zones.filter(code__startswith='fileshare_').count()
    other_count = all_zones.exclude(code__startswith='loomline_').exclude(code__startswith='fileshare_').count()

    print(f"\n📊 Zone Statistics:")
    print(f"  Total Zones: {all_zones.count()}")
    print(f"  LoomLine: {loomline_count}")
    print(f"  FileShara: {fileshare_count}")
    print(f"  Other Apps: {other_count}")

    return True

def test_sample_ads_generation():
    """Teste die Generierung von Beispielanzeigen"""
    print("\n🎨 Testing Sample Ads Generation:")
    print("=" * 50)

    # Teste LoomLine Zone
    loomline_zone = AdZone.objects.filter(code__startswith='loomline_').first()
    if loomline_zone:
        ads = get_sample_ads_for_zone(loomline_zone, 'loomline')
        print(f"\nLoomLine Zone: {loomline_zone.name}")
        for i, ad in enumerate(ads, 1):
            print(f"  {i}. {ad['name']} (Weight: {ad['weight']})")
            print(f"     Campaign: {ad['campaign']}")
            print(f"     HTML: {len(ad['html_content'])} chars")

    # Teste FileShara Zone
    fileshare_zone = AdZone.objects.filter(code__startswith='fileshare_').first()
    if fileshare_zone:
        ads = get_sample_ads_for_zone(fileshare_zone, 'fileshare')
        print(f"\nFileShara Zone: {fileshare_zone.name}")
        for i, ad in enumerate(ads, 1):
            print(f"  {i}. {ad['name']} (Weight: {ad['weight']})")
            print(f"     Campaign: {ad['campaign']}")
            print(f"     HTML: {len(ad['html_content'])} chars")

def generate_usage_examples():
    """Generiere Nutzungsbeispiele für die URLs"""
    print("\n🔗 URL Examples for Testing:")
    print("=" * 50)

    base_url = "http://127.0.0.1:8000/loomads/examples/"

    print(f"Examples Overview (All Apps): {base_url}")
    print(f"LoomLine Only: {base_url}?app=loomline")
    print(f"FileShara Only: {base_url}?app=fileshare")
    print(f"Videos Only: {base_url}?app=videos")

    # Beispiel-Zonen für Details
    sample_zones = AdZone.objects.filter(is_active=True)[:5]
    print(f"\nZone Detail Examples:")
    for zone in sample_zones:
        print(f"  {zone.name}: {base_url}zone/{zone.id}/")

def main():
    """Hauptfunktion"""
    try:
        test_examples_integration()
        test_sample_ads_generation()
        generate_usage_examples()

        print("\n✅ All tests completed successfully!")
        print("\nNext Steps:")
        print("1. Visit http://127.0.0.1:8000/loomads/examples/ to see the new grouped interface")
        print("2. Filter by apps using the dropdown menu")
        print("3. Click on zone tiles to see app-specific sample ads")
        print("4. Copy HTML code for integration templates")

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
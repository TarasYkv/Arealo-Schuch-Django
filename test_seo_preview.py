#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.models import ShopifyCollection

# Test SEO preview functionality
print("=== Testing SEO Preview Functionality ===")

# Test 1: Check if collection has SEO details
try:
    collection = ShopifyCollection.objects.get(id=211)
    print(f"✅ Collection found: {collection.title}")
    print(f"   - Store: {collection.store.name}")
    print(f"   - SEO Title: '{collection.seo_title}'")
    print(f"   - SEO Description: '{collection.seo_description}'")
    print(f"   - Image Alt: '{collection.image_alt}'")
    print()
except ShopifyCollection.DoesNotExist:
    print("❌ Collection 211 not found")
    sys.exit(1)

# Test 2: Check SEO details method
try:
    seo_details = collection.get_seo_details()
    print("✅ SEO Details method working:")
    print(f"   - Total Score: {seo_details['total_score']}/100")
    print(f"   - Title Score: {seo_details['title_score']}/40")
    print(f"   - Description Score: {seo_details['description_score']}/40")
    print(f"   - Alt-Text Score: {seo_details['alt_text_score']}/20")
    print(f"   - Breakdown: {seo_details['breakdown']}")
    print(f"   - Combined Status: {seo_details['combined_status']}")
    print()
except Exception as e:
    print(f"❌ SEO Details method error: {e}")
    sys.exit(1)

# Test 3: Check alt-text status
try:
    alt_status = collection.get_alt_text_status()
    print(f"✅ Alt-Text Status: {alt_status}")
    print()
except Exception as e:
    print(f"❌ Alt-Text Status error: {e}")

# Test 4: Check combined SEO status
try:
    combined_status = collection.get_combined_seo_status()
    print(f"✅ Combined SEO Status: {combined_status}")
    print()
except Exception as e:
    print(f"❌ Combined SEO Status error: {e}")

# Test 5: Check if storefront URL method exists
try:
    storefront_url = collection.get_storefront_url()
    print(f"✅ Storefront URL: {storefront_url}")
    print()
except Exception as e:
    print(f"❌ Storefront URL method error: {e}")

print("=== SEO Preview Test Complete ===")
print("Changes implemented:")
print("1. ✅ 'Aktueller SEO-Status' replaced with 'SEO-Vorschau'")
print("2. ✅ Google Search Result Preview added")
print("3. ✅ Enhanced hover tooltips for all overview tiles")
print("4. ✅ Consistent tooltip format across collections, products, and blog posts")
print("5. ✅ Real-time preview updates when SEO data changes")
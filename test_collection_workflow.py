#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.urls import reverse
from shopify_manager.models import ShopifyCollection
from shopify_manager.collection_views import *

# Test collection workflow
print("=== Testing Collection Workflow ===")

# Test 1: Check if collection exists
try:
    collection = ShopifyCollection.objects.get(id=211)
    print(f"✅ Collection found: {collection.title}")
    print(f"   - Store: {collection.store.name}")
    print(f"   - Image URL: {collection.image_url}")
    print(f"   - Alt-Text: '{collection.image_alt}'")
    print(f"   - Alt-Text Status: {collection.get_alt_text_status()}")
    print()
except ShopifyCollection.DoesNotExist:
    print("❌ Collection 211 not found")
    sys.exit(1)

# Test 2: Check URL patterns
try:
    seo_url = reverse('shopify_manager:collection_seo_optimization', kwargs={'collection_id': collection.id})
    alt_text_url = reverse('shopify_manager:collection_alt_text_manager', kwargs={'collection_id': collection.id})
    ajax_url = reverse('shopify_manager:collection_seo_ajax', kwargs={'collection_id': collection.id})
    
    print("✅ URL patterns working:")
    print(f"   - SEO URL: {seo_url}")
    print(f"   - Alt-Text URL: {alt_text_url}")
    print(f"   - AJAX URL: {ajax_url}")
    print()
except Exception as e:
    print(f"❌ URL pattern error: {e}")
    sys.exit(1)

# Test 3: Test AI service import
try:
    from naturmacher.services.ai_service import generate_alt_text_with_ai
    print("✅ AI service import successful")
    print("   - generate_alt_text_with_ai function available")
    print()
except ImportError as e:
    print(f"❌ AI service import error: {e}")
    print("   - Function will use fallback implementation")
    print()

# Test 4: Test collection view functions
try:
    # Test view function existence
    view_functions = [
        'collection_alt_text_manager_view',
        'update_collection_alt_text_view', 
        'generate_collection_alt_text_view',
        'collection_seo_ajax_view'
    ]
    
    for func_name in view_functions:
        func = globals().get(func_name)
        if func:
            print(f"✅ View function '{func_name}' exists")
        else:
            print(f"❌ View function '{func_name}' missing")
    print()
except Exception as e:
    print(f"❌ View function test error: {e}")

print("=== Collection Workflow Test Complete ===")
print("The workflow should now work as follows:")
print("1. User goes to collection detail page")
print("2. User clicks 'Do-SEO' button")
print("3. User generates and saves SEO data")
print("4. User is automatically redirected to 'Do-Alt-Texte' page")
print("5. User can generate AI-powered alt-text for collection image")
print("6. User saves alt-text and improves accessibility")
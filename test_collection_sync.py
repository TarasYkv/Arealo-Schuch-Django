#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.models import ShopifyCollection
from shopify_manager.shopify_api import ShopifyCollectionSync, ShopifyAPIClient

# Test Collection 211
c = ShopifyCollection.objects.get(id=211)
print(f"Collection: {c.title}")
print(f"Shopify ID: {c.shopify_id}")
print(f"Store: {c.store.name}")
print(f"Current SEO Title: '{c.seo_title}'")
print(f"Current SEO Description: '{c.seo_description}'")
print()

# Test 1: Test API Connection
api = ShopifyAPIClient(c.store)
print("=== Test 1: API Connection ===")
success, message = api.test_connection()
print(f"Connection test: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print()

# Test 2: Test collection metafields
print("=== Test 2: Collection Metafields ===")
success, metafields, message = api.get_collection_metafields(c.shopify_id)
print(f"Metafields fetch: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print(f"Found {len(metafields)} metafields")
for mf in metafields:
    print(f"  - {mf.get('namespace', 'N/A')}:{mf.get('key', 'N/A')} = {mf.get('value', 'N/A')[:50]}...")
print()

# Test 3: Test collection sync
print("=== Test 3: Collection Sync ===")
sync = ShopifyCollectionSync(c.store)
try:
    # Set test SEO data
    c.seo_title = "Test SEO Title"
    c.seo_description = "Test SEO Description for synchronization"
    c.save()
    
    success, sync_message = sync.sync_collection_to_shopify(c)
    print(f"Sync result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Sync message: {sync_message}")
    
    if not success:
        print(f"Collection sync_error: {c.sync_error}")
        
except Exception as e:
    print(f"❌ Exception during sync: {e}")
    import traceback
    traceback.print_exc()
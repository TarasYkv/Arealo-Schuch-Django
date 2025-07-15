#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.models import ShopifyCollection
from shopify_manager.shopify_api import ShopifyAPIClient

# Test Collection 211
c = ShopifyCollection.objects.get(id=211)
api = ShopifyAPIClient(c.store)

print(f"Collection: {c.title}")
print(f"Shopify ID: {c.shopify_id}")
print(f"Store: {c.store.name}")
print()

# Test updating only SEO metafields
print("=== Test: Update SEO Metafields Only ===")

# Test 1: Update SEO Title
print("1. Updating SEO Title metafield...")
success, message = api.update_collection_metafield(
    c.shopify_id, 
    'global', 
    'title_tag',
    'NEW Test SEO Title from sync test', 
    'single_line_text_field'
)
print(f"SEO Title update: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print()

# Test 2: Update SEO Description
print("2. Updating SEO Description metafield...")
success, message = api.update_collection_metafield(
    c.shopify_id, 
    'global', 
    'description_tag',
    'NEW Test SEO Description from sync test', 
    'multi_line_text_field'
)
print(f"SEO Description update: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print()

# Test 3: Verify metafields
print("3. Verifying updated metafields...")
success, metafields, message = api.get_collection_metafields(c.shopify_id)
print(f"Metafields fetch: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Found {len(metafields)} metafields:")
for mf in metafields:
    print(f"  - {mf.get('namespace', 'N/A')}:{mf.get('key', 'N/A')} = {mf.get('value', 'N/A')}")
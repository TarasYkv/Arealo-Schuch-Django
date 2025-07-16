#!/usr/bin/env python
import os
import sys
import django
import json

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth.models import User
from shopify_manager.models import ShopifyCollection
from shopify_manager.shopify_api import ShopifyAPIClient

# Debug Collection Structure
print("=== Debugging Collection Structure ==")

# Get test data
collection = ShopifyCollection.objects.get(id=211)
user = collection.store.user

print(f"Collection: {collection.title}")
print(f"Collection ID: {collection.shopify_id}")
print(f"Local Alt-Text: '{collection.image_alt}'")
print(f"Image URL: {collection.image_url}")
print()

# Get current collection from Shopify
try:
    shopify_api = ShopifyAPIClient(collection.store)
    
    print("=== Fetching current collection from Shopify ===")
    success, shopify_collection, message = shopify_api.fetch_single_collection(collection.shopify_id)
    
    if success:
        print(f"✅ Collection found: {shopify_collection.get('title', 'N/A')}")
        print(f"Handle: {shopify_collection.get('handle', 'N/A')}")
        print(f"ID: {shopify_collection.get('id', 'N/A')}")
        
        # Check image structure
        image_data = shopify_collection.get('image')
        if image_data:
            print(f"Image data found:")
            print(f"  - Alt: '{image_data.get('alt', 'N/A')}'")
            print(f"  - Src: {image_data.get('src', 'N/A')}")
            print(f"  - Width: {image_data.get('width', 'N/A')}")
            print(f"  - Height: {image_data.get('height', 'N/A')}")
        else:
            print("❌ No image data found")
        
        # Check metafields
        print(f"\n=== Checking metafields ===")
        metafields_success, metafields, metafields_message = shopify_api.get_collection_metafields(collection.shopify_id)
        
        if metafields_success:
            print(f"Found {len(metafields)} metafields:")
            for mf in metafields:
                if isinstance(mf, dict):
                    namespace = mf.get('namespace', 'N/A')
                    key = mf.get('key', 'N/A')
                    value = mf.get('value', 'N/A')
                    print(f"  - {namespace}.{key}: '{value}'")
        else:
            print(f"❌ Metafields error: {metafields_message}")
            
    else:
        print(f"❌ Collection fetch failed: {message}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
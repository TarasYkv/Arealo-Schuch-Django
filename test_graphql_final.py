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

# Test final GraphQL implementation
print("=== Testing Final GraphQL Implementation ===")

collection = ShopifyCollection.objects.get(id=211)
shopify_api = ShopifyAPIClient(collection.store)

new_alt_text = "Vision AI: Drei stilisierte Weihnachtsbäume auf rotem Aquarell-Hintergrund"

print(f"Collection: {collection.title}")
print(f"Collection ID: {collection.shopify_id}")
print(f"New Alt-Text: '{new_alt_text}'")
print()

# Test new GraphQL method
print("=== Testing GraphQL Alt-Text Update ===")
try:
    success, message = shopify_api.update_collection_image_alt_text(
        collection.shopify_id,
        new_alt_text
    )
    
    print(f"Success: {'✅' if success else '❌'} {success}")
    print(f"Message: {message}")
    
    if success:
        # Update local record
        collection.image_alt = new_alt_text
        collection.needs_sync = False
        collection.sync_error = ""
        collection.save()
        print("✅ Local record updated")
        
        # Verify by fetching from Shopify
        print("\n=== Verifying update in Shopify ===")
        verify_success, shopify_collection, verify_message = shopify_api.fetch_single_collection(collection.shopify_id)
        
        if verify_success:
            image_data = shopify_collection.get('image', {})
            shopify_alt_text = image_data.get('alt', 'N/A')
            print(f"Shopify Alt-Text: '{shopify_alt_text}'")
            
            if shopify_alt_text == new_alt_text:
                print("✅ Alt-Text successfully updated in Shopify!")
            else:
                print(f"❌ Alt-Text mismatch: Expected '{new_alt_text}', got '{shopify_alt_text}'")
        else:
            print(f"❌ Verification failed: {verify_message}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
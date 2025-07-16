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

# Test Alt-Text Sync
print("=== Testing Alt-Text Sync ==")

# Get test data
collection = ShopifyCollection.objects.get(id=211)
user = collection.store.user

print(f"Collection: {collection.title}")
print(f"Collection ID: {collection.shopify_id}")
print(f"Current Alt-Text: '{collection.image_alt}'")
print(f"Image URL: {collection.image_url}")
print()

# Test manual sync
try:
    shopify_api = ShopifyAPIClient(collection.store)
    
    # Test Alt-Text
    new_alt_text = "Test Alt-Text für KI-Vision - Drei Weihnachtsbäume"
    
    print(f"Testing Shopify Metafield sync with Alt-Text: '{new_alt_text}'")
    
    # Metafield-Ansatz
    success, message = shopify_api.update_collection_metafield(
        collection.shopify_id,
        'custom',  # namespace
        'image_alt_text',  # key  
        new_alt_text,  # value
        'single_line_text_field'  # type
    )
    
    print(f"Metafield Update - Success: {success}, Message: {message}")
    
    if success:
        print("✅ Metafield sync successful!")
        
        # Update local record
        collection.image_alt = new_alt_text
        collection.needs_sync = False
        collection.sync_error = ""
        collection.save()
        print("✅ Local record updated")
        
    else:
        print("❌ Metafield sync failed!")
        print(f"Error: {message}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
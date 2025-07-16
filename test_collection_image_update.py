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

# Test different approaches to update collection image alt-text
print("=== Testing Collection Image Alt-Text Update ===")

collection = ShopifyCollection.objects.get(id=211)
shopify_api = ShopifyAPIClient(collection.store)

new_alt_text = "KI-generierte Beschreibung: Drei stilisierte Weihnachtsbäume"

print(f"Collection: {collection.title}")
print(f"New Alt-Text: '{new_alt_text}'")
print()

# Approach 1: Update only image data without other fields
print("=== Approach 1: Minimal collection update ===")
try:
    shopify_data = {
        'collection': {
            'image': {
                'alt': new_alt_text
            }
        }
    }
    
    print(f"Sending: {shopify_data}")
    
    response = shopify_api._make_request(
        'PUT',
        f"{shopify_api.base_url}/collections/{collection.shopify_id}.json",
        json=shopify_data,
        timeout=15
    )
    
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Approach 1 successful!")
        data = response.json()
        updated_collection = data.get('collection', {})
        updated_image = updated_collection.get('image', {})
        print(f"Updated Alt-Text: '{updated_image.get('alt', 'N/A')}'")
    else:
        print("❌ Approach 1 failed")
        try:
            error_data = response.json() if 'json' in response.headers.get('content-type', '') else response.text
            print(f"Error: {error_data}")
        except:
            print(f"Raw Error: {response.text}")
            
except Exception as e:
    print(f"❌ Approach 1 Exception: {e}")

print("\n" + "="*50 + "\n")

# Approach 2: Update with minimal required fields
print("=== Approach 2: Update with required fields ===")
try:
    shopify_data = {
        'collection': {
            'id': int(collection.shopify_id),
            'title': collection.title,  # Required field
            'image': {
                'alt': new_alt_text,
                'src': collection.image_url  # Include src
            }
        }
    }
    
    print(f"Sending: {shopify_data}")
    
    response = shopify_api._make_request(
        'PUT',
        f"{shopify_api.base_url}/collections/{collection.shopify_id}.json",
        json=shopify_data,
        timeout=15
    )
    
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Approach 2 successful!")
        data = response.json()
        updated_collection = data.get('collection', {})
        updated_image = updated_collection.get('image', {})
        print(f"Updated Alt-Text: '{updated_image.get('alt', 'N/A')}'")
    else:
        print("❌ Approach 2 failed")
        try:
            error_data = response.json() if 'json' in response.headers.get('content-type', '') else response.text
            print(f"Error: {error_data}")
        except:
            print(f"Raw Error: {response.text}")
            
except Exception as e:
    print(f"❌ Approach 2 Exception: {e}")

print("\n" + "="*50 + "\n")

# Approach 3: Use the existing update_collection method with specific parameters
print("=== Approach 3: Use existing update_collection method ===")
try:
    collection_data = {
        'title': collection.title,
        'image': {
            'alt': new_alt_text,
            'src': collection.image_url
        }
    }
    
    success, result, message = shopify_api.update_collection(
        collection.shopify_id,
        collection_data,
        seo_only=False
    )
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    
    if success and result:
        updated_image = result.get('image', {})
        print(f"Updated Alt-Text: '{updated_image.get('alt', 'N/A')}'")
        
except Exception as e:
    print(f"❌ Approach 3 Exception: {e}")
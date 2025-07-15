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

# Test creating a metafield directly
print("=== Test: Creating Collection Metafield ===")

metafield_data = {
    'metafield': {
        'namespace': 'global',
        'key': 'title_tag',
        'value': 'Test SEO Title',
        'type': 'single_line_text_field'
    }
}

try:
    response = api._make_request(
        'POST',
        f"{api.base_url}/collections/{c.shopify_id}/metafields.json",
        json=metafield_data,
        timeout=10
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    print(f"Response text: '{response.text}'")
    
    if response.headers.get('content-type', '').startswith('application/json'):
        print("Response is JSON - parsing...")
        data = response.json()
        print(f"Parsed data: {data}")
    else:
        print("Response is NOT JSON")
        
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
    
print()

# Test 2: Try updating collection basic data (without metafields)
print("=== Test: Updating Collection Basic Data ===")
try:
    collection_data = {
        'collection': {
            'id': int(c.shopify_id),
            'title': c.title,
            'handle': c.handle,
            'description': c.description,
            'published': c.published,
            'sort_order': c.sort_order,
        }
    }
    
    response = api._make_request(
        'PUT',
        f"{api.base_url}/collections/{c.shopify_id}.json",
        json=collection_data,
        timeout=15
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response text: '{response.text[:200]}...'")
    
    if response.status_code == 200:
        print("✅ Basic collection update successful")
    else:
        print(f"❌ Basic collection update failed: {response.status_code}")
        
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
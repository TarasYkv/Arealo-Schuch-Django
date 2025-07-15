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
print(f"Base URL: {api.base_url}")

# Test API connection
try:
    response = api._make_request('GET', f'{api.base_url}/collections/{c.shopify_id}.json')
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        print("✅ API Connection successful")
        data = response.json()
        print(f"Current title: {data['collection']['title']}")
        print(f"Current handle: {data['collection']['handle']}")
    else:
        print("❌ API Connection failed")
        print(f'Response: {response.text}')
except Exception as e:
    print(f'❌ API Error: {e}')
    import traceback
    traceback.print_exc()
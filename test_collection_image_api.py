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

# Test alternative API endpoints for Collection Images
print("=== Testing Collection Image API Endpoints ===")

collection = ShopifyCollection.objects.get(id=211)
shopify_api = ShopifyAPIClient(collection.store)

new_alt_text = "Final test: Drei Weihnachtsbäume auf rotem Hintergrund"

print(f"Collection: {collection.title}")
print(f"Collection ID: {collection.shopify_id}")
print(f"New Alt-Text: '{new_alt_text}'")
print()

# Check if there's a specific collection images endpoint
print("=== Testing collection images endpoint ===")
try:
    # Try to get collection images
    response = shopify_api._make_request(
        'GET',
        f"{shopify_api.base_url}/collections/{collection.shopify_id}/images.json",
        timeout=15
    )
    
    print(f"GET /collections/{collection.shopify_id}/images.json - Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Images found: {data}")
    else:
        print(f"Images endpoint not available: {response.text}")
        
except Exception as e:
    print(f"Images endpoint error: {e}")

print("\n" + "="*50 + "\n")

# Try updating collection with PATCH instead of PUT
print("=== Testing PATCH method ===")
try:
    shopify_data = {
        'collection': {
            'image': {
                'alt': new_alt_text
            }
        }
    }
    
    response = shopify_api._make_request(
        'PATCH',
        f"{shopify_api.base_url}/collections/{collection.shopify_id}.json",
        json=shopify_data,
        timeout=15
    )
    
    print(f"PATCH Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ PATCH successful!")
        data = response.json()
        updated_collection = data.get('collection', {})
        updated_image = updated_collection.get('image', {})
        print(f"Updated Alt-Text: '{updated_image.get('alt', 'N/A')}'")
    else:
        print("❌ PATCH failed")
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"❌ PATCH Exception: {e}")

print("\n" + "="*50 + "\n")

# Check if the collection is editable (maybe it's protected)
print("=== Testing collection permissions ===")
try:
    # Get current collection details
    response = shopify_api._make_request(
        'GET',
        f"{shopify_api.base_url}/collections/{collection.shopify_id}.json",
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        collection_data = data.get('collection', {})
        print(f"Collection type: {collection_data.get('collection_type', 'N/A')}")
        print(f"Published: {collection_data.get('published', 'N/A')}")
        print(f"Handle: {collection_data.get('handle', 'N/A')}")
        print(f"Admin URL: {collection_data.get('admin_graphql_api_id', 'N/A')}")
        
except Exception as e:
    print(f"Permission check error: {e}")

print("\n" + "="*50 + "\n")

# Test using GraphQL API instead (if available)
print("=== Testing GraphQL mutation ===")
try:
    # Check if GraphQL API is available
    graphql_query = """
    mutation collectionUpdate($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection {
          id
          title
          image {
            altText
            url
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    variables = {
        "input": {
            "id": f"gid://shopify/Collection/{collection.shopify_id}",
            "image": {
                "altText": new_alt_text
            }
        }
    }
    
    graphql_data = {
        "query": graphql_query,
        "variables": variables
    }
    
    response = shopify_api._make_request(
        'POST',
        f"{shopify_api.base_url.replace('/admin/api/2023-10', '')}/admin/api/2023-10/graphql.json",
        json=graphql_data,
        timeout=15
    )
    
    print(f"GraphQL Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"GraphQL Response: {data}")
        
        if 'data' in data and 'collectionUpdate' in data['data']:
            update_data = data['data']['collectionUpdate']
            if update_data.get('collection'):
                image_data = update_data['collection'].get('image', {})
                print(f"✅ GraphQL successful! Alt-Text: '{image_data.get('altText', 'N/A')}'")
            else:
                print(f"❌ GraphQL errors: {update_data.get('userErrors', [])}")
        else:
            print("❌ GraphQL response format unexpected")
    else:
        print(f"❌ GraphQL failed: {response.text}")
        
except Exception as e:
    print(f"❌ GraphQL Exception: {e}")
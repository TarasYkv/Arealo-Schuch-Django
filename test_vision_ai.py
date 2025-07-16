#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth.models import User
from shopify_manager.models import ShopifyCollection

# Test AI Service with Vision
print("=== Testing AI Vision Service ==")

# Get test data
collection = ShopifyCollection.objects.get(id=211)
user = collection.store.user

print(f"Collection: {collection.title}")
print(f"Image URL: {collection.image_url}")
print(f"User: {user.username}")
print(f"OpenAI Key: {'✅ Available' if user.openai_api_key else '❌ Not set'}")
print()

# Test the updated AI service with vision
try:
    from naturmacher.services.ai_service import generate_alt_text_with_ai
    
    print("Testing Vision AI Service...")
    success, alt_text, message = generate_alt_text_with_ai(
        image_url=collection.image_url,
        context_title=collection.title,
        context_description=collection.description or "Weihnachtsgeschenke und festliche Artikel",
        user=user,
        content_type='collection'
    )
    
    print(f"Success: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Alt-Text: '{alt_text}'")
    print(f"Message: {message}")
    print(f"Length: {len(alt_text)} characters")
    print()
    
    # Test multiple generations to see variety
    print("Testing multiple generations for variety...")
    for i in range(3):
        success, alt_text, message = generate_alt_text_with_ai(
            image_url=collection.image_url,
            context_title=collection.title,
            context_description=collection.description or "Weihnachtsgeschenke",
            user=user,
            content_type='collection'
        )
        print(f"Generation {i+1}: '{alt_text}' ({len(alt_text)} chars)")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
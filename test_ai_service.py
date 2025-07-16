#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth.models import User
from shopify_manager.models import ShopifyCollection

# Test AI Service
print("=== Testing AI Service for Alt-Text Generation ===")

# Get test user and collection
try:
    collection = ShopifyCollection.objects.get(id=211)
    user = collection.store.user
    print(f"✅ Test data found:")
    print(f"   - Collection: {collection.title}")
    print(f"   - User: {user.username}")
    print(f"   - Store: {collection.store.name}")
    print(f"   - Image URL: {collection.image_url}")
    print()
except Exception as e:
    print(f"❌ Test data error: {e}")
    sys.exit(1)

# Test AI Service function
try:
    from naturmacher.services.ai_service import generate_alt_text_with_ai
    print("✅ AI Service imported successfully")
    
    # Test with collection data
    success, alt_text, message = generate_alt_text_with_ai(
        image_url=collection.image_url,
        context_title=collection.title,
        context_description=collection.description or "Weihnachtsgeschenke und festliche Artikel",
        user=user,
        content_type='collection'
    )
    
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Alt-Text: '{alt_text}'")
    print(f"Message: {message}")
    print()
    
except ImportError as e:
    print(f"❌ AI Service import error: {e}")
    print("This means the AI service is not available")
    print()
except Exception as e:
    print(f"❌ AI Service execution error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test user API keys
print("=== Testing User API Keys ===")
try:
    openai_key = getattr(user, 'openai_api_key', None)
    anthropic_key = getattr(user, 'anthropic_api_key', None)
    
    print(f"OpenAI API Key: {'✅ Available' if openai_key else '❌ Not set'}")
    print(f"Anthropic API Key: {'✅ Available' if anthropic_key else '❌ Not set'}")
    
    if not openai_key and not anthropic_key:
        print("⚠️ No API keys available - will use fallback generation")
    print()
except Exception as e:
    print(f"❌ API Key check error: {e}")
    print()

# Test fallback generation
print("=== Testing Fallback Generation ===")
try:
    collection_title = collection.title
    collection_description = collection.description or "Weihnachtsgeschenke und festliche Artikel"
    
    # Fallback logic from the view
    suggested_alt_text = f"Kategorie-Bild für {collection_title}"
    if collection_description:
        desc_words = collection_description.split()[:5]
        suggested_alt_text = f"{collection_title} - {' '.join(desc_words)}"
    
    if len(suggested_alt_text) > 125:
        suggested_alt_text = suggested_alt_text[:122] + "..."
    
    print(f"✅ Fallback Alt-Text: '{suggested_alt_text}'")
    print(f"   - Length: {len(suggested_alt_text)} characters")
    print()
except Exception as e:
    print(f"❌ Fallback generation error: {e}")
    print()

print("=== Debugging URL and View ===")
try:
    from django.urls import reverse
    
    # Test URL generation
    url = reverse('shopify_manager:generate_collection_alt_text', kwargs={'collection_id': collection.id})
    print(f"✅ Generate Alt-Text URL: {url}")
    
    # Test view function
    from shopify_manager.collection_views import generate_collection_alt_text_view
    print(f"✅ View function exists: {generate_collection_alt_text_view}")
    print()
except Exception as e:
    print(f"❌ URL/View test error: {e}")
    print()
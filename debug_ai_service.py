#!/usr/bin/env python
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth.models import User
from shopify_manager.models import ShopifyCollection

# Test AI Service with detailed debugging
print("=== Debugging AI Service ===")

# Get test data
collection = ShopifyCollection.objects.get(id=211)
user = collection.store.user

print(f"Collection: {collection.title}")
print(f"User: {user.username}")
print(f"OpenAI Key: {user.openai_api_key[:10]}..." if user.openai_api_key else "None")
print(f"Anthropic Key: {user.anthropic_api_key[:10]}..." if user.anthropic_api_key else "None")
print()

# Test the new text API functions directly
try:
    from naturmacher.services.ai_service import call_openai_api_for_text
    
    system_prompt = "Du bist ein Experte für Alt-Text-Generierung. Erstelle einen kurzen, beschreibenden Alt-Text."
    user_prompt = f"Erstelle einen Alt-Text für ein Weihnachts-Kategorie-Bild mit dem Titel: {collection.title}"
    
    print("Testing OpenAI API directly...")
    result = call_openai_api_for_text(user.openai_api_key, system_prompt, user_prompt)
    print(f"Result: {result}")
    print()
    
except Exception as e:
    print(f"Error testing OpenAI API: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test fallback in view
try:
    print("Testing fallback logic...")
    collection_title = collection.title
    collection_description = collection.description or "Weihnachtsgeschenke und festliche Artikel"
    
    # Enhanced fallback
    suggested_alt_text = f"Kategorie-Bild für {collection_title}"
    if collection_description:
        desc_words = collection_description.split()[:5]
        suggested_alt_text = f"{collection_title} - {' '.join(desc_words)}"
    
    if len(suggested_alt_text) > 125:
        suggested_alt_text = suggested_alt_text[:122] + "..."
    
    print(f"Fallback result: '{suggested_alt_text}'")
    print(f"Length: {len(suggested_alt_text)} chars")
    print()
    
except Exception as e:
    print(f"Fallback error: {e}")
    print()

# Test complete alt-text generation function
try:
    from naturmacher.services.ai_service import generate_alt_text_with_ai
    
    print("Testing complete function with debug...")
    success, alt_text, message = generate_alt_text_with_ai(
        image_url=collection.image_url,
        context_title=collection.title,
        context_description=collection.description or "Weihnachtsgeschenke",
        user=user,
        content_type='collection'
    )
    
    print(f"Success: {success}")
    print(f"Alt-Text: '{alt_text}'")
    print(f"Message: {message}")
    
except Exception as e:
    print(f"Complete function error: {e}")
    import traceback
    traceback.print_exc()
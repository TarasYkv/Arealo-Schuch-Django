#!/usr/bin/env python3
"""
Debug-Script für OpenAI Vision API
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
django.setup()

import requests
import json
from accounts.models import CustomUser
from naturmacher.utils.api_helpers import get_user_api_key
from shopify_manager.models import ShopifyProduct

def debug_vision_api():
    """Detailliertes Debugging der Vision API"""
    try:
        print("=== OpenAI Vision API Debug ===")
        
        user = CustomUser.objects.filter(is_active=True).first()
        product = ShopifyProduct.objects.first()
        
        if not user or not product:
            print("❌ User oder Produkt fehlt")
            return
        
        api_key = get_user_api_key(user, 'openai')
        if not api_key:
            print("❌ Kein API-Key")
            return
        
        # Einfaches Test-Bild
        image_url = "https://picsum.photos/200/200"
        
        prompt = f"""Analysiere dieses Bild und erstelle einen Alt-Text.
        
Produktkontext:
- Titel: {product.title}
- Hersteller: {product.vendor or 'Unbekannt'}

Antworte nur mit dem Alt-Text, maximal 100 Zeichen."""

        print(f"🔄 API Request...")
        print(f"Image URL: {image_url}")
        print(f"Prompt: {prompt[:100]}...")
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',  # Aktueller Vision-fähiger Model
                'messages': [
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': prompt},
                            {'type': 'image_url', 'image_url': {'url': image_url}}
                        ]
                    }
                ],
                'max_tokens': 100,
                'temperature': 0.3
            },
            timeout=30
        )
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"📋 Full Response: {json.dumps(result, indent=2)}")
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"✅ Content: '{content}'")
                
                if content and content.strip():
                    print(f"✅ Alt-Text erfolgreich: {content.strip()}")
                    return True
                else:
                    print("❌ Content ist leer")
                    return False
            else:
                print("❌ Keine choices in response")
                return False
        else:
            print(f"❌ API Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    debug_vision_api()
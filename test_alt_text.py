#!/usr/bin/env python3
"""
Test-Script für Alt-Text-Generierung in der Shopify App
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
django.setup()

from accounts.models import CustomUser
from shopify_manager.models import ShopifyProduct

def test_alt_text_generation():
    """Testet die Alt-Text-Generierung für ein Shopify-Produkt"""
    try:
        print("=== Alt-Text Generierung Test ===")
        
        # Hole User und Produkt
        user = CustomUser.objects.filter(is_active=True).first()
        if not user:
            print("❌ Kein aktiver User gefunden")
            return
        
        print(f"✓ Test User: {user.username}")
        
        # Hole erstes Produkt
        product = ShopifyProduct.objects.first()
        if not product:
            print("❌ Kein Shopify-Produkt gefunden")
            return
        
        print(f"✓ Test Produkt: {product.title}")
        
        # Teste Alt-Text-Generierung
        from shopify_manager.views import generate_alt_text_with_ai
        
        # Test mit einer Beispiel-Bild-URL
        test_image_url = "https://via.placeholder.com/400x300.jpg?text=Test+Product"
        print(f"🔄 Teste Alt-Text für: {test_image_url}")
        
        alt_text = generate_alt_text_with_ai(product, test_image_url, user)
        
        if alt_text:
            print(f"✅ Alt-Text generiert: {alt_text}")
            return True
        else:
            print("❌ Kein Alt-Text generiert")
            return False
        
    except Exception as e:
        print(f"❌ Fehler beim Alt-Text Test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_openai_vision_directly():
    """Testet die OpenAI Vision API direkt"""
    try:
        print("\n=== OpenAI Vision Direct Test ===")
        
        user = CustomUser.objects.filter(is_active=True).first()
        product = ShopifyProduct.objects.first()
        
        if not user or not product:
            print("❌ User oder Produkt fehlt")
            return False
        
        from shopify_manager.views import generate_alt_text_openai_vision
        from naturmacher.utils.api_helpers import get_user_api_key
        
        api_key = get_user_api_key(user, 'openai')
        if not api_key:
            print("❌ Kein OpenAI API-Key")
            return False
        
        # Test mit öffentlichem Bild
        test_image = "https://picsum.photos/400/300"  # Zufälliges Bild
        print(f"🔄 Teste Vision API mit: {test_image}")
        
        alt_text = generate_alt_text_openai_vision(product, test_image, api_key)
        
        if alt_text:
            print(f"✅ Vision Alt-Text: {alt_text}")
            return True
        else:
            print("❌ Vision API lieferte keinen Text")
            return False
            
    except Exception as e:
        print(f"❌ Vision Test Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Starte Alt-Text Diagnose...\n")
    
    # Test 1: Allgemeine Alt-Text-Generierung
    general_test = test_alt_text_generation()
    
    # Test 2: Direkte OpenAI Vision API
    vision_test = test_openai_vision_directly()
    
    if general_test and vision_test:
        print("\n🎉 Alt-Text-Generierung funktioniert korrekt!")
    elif general_test:
        print("\n⚠️ Alt-Text funktioniert allgemein, aber Vision API hat Probleme")
    elif vision_test:
        print("\n⚠️ Vision API funktioniert, aber allgemeine Funktion hat Probleme")
    else:
        print("\n❌ Alt-Text-Generierung hat Probleme")
    
    print("\nDiagnose beendet.")
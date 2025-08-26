#!/usr/bin/env python3
"""
Test-Script für OpenAI API-Integration
Prüft ob die API-Keys korrekt abgerufen und verwendet werden
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
django.setup()

import requests
from accounts.models import CustomUser
from naturmacher.utils.api_helpers import get_user_api_key

def test_api_key_retrieval():
    """Testet den API-Key Abruf für den ersten aktiven User"""
    print("=== OpenAI API Test ===")
    
    # Hole ersten aktiven User
    try:
        user = CustomUser.objects.filter(is_active=True).first()
        if not user:
            print("❌ Kein aktiver User gefunden")
            return False
        
        print(f"✓ Test User: {user.username}")
        
        # Prüfe OpenAI API-Key
        openai_key = get_user_api_key(user, 'openai')
        if openai_key:
            # Verberge den Key für Sicherheit
            masked_key = f"{openai_key[:10]}...{openai_key[-4:]}"
            print(f"✓ OpenAI Key gefunden: {masked_key}")
            
            # Test API-Call
            return test_openai_api_call(openai_key)
        else:
            print("❌ Kein OpenAI API-Key für User gefunden")
            
            # Prüfe direkt im User-Modell
            if hasattr(user, 'openai_api_key'):
                raw_key = user.openai_api_key
                if raw_key and raw_key.strip():
                    print(f"⚠️ Raw key im User-Modell gefunden: {raw_key[:10] if len(raw_key) > 10 else raw_key}")
                else:
                    print("❌ Auch raw key ist leer oder None")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim User-Test: {e}")
        return False

def test_openai_api_call(api_key):
    """Testet einen echten API-Call zu OpenAI"""
    try:
        print("🔄 Teste OpenAI API-Call...")
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o-mini',  # Günstiges Modell für Test
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Antworte nur mit "TEST OK" auf Deutsch.'
                    }
                ],
                'max_tokens': 10,
                'temperature': 0
            },
            timeout=30
        )
        
        print(f"📊 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content'].strip()
                print(f"✅ API Response: {content}")
                return True
            else:
                print(f"❌ Unerwartete API-Antwort Struktur: {result}")
                return False
        else:
            print(f"❌ API-Fehler {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API-Call Fehler: {e}")
        return False

def test_seo_generation():
    """Testet die SEO-Generierung aus der Shopify App"""
    try:
        print("\n=== SEO Generierung Test ===")
        
        from shopify_manager.ai_seo_service import OpenAIService, get_ai_service
        
        user = CustomUser.objects.filter(is_active=True).first()
        if not user:
            print("❌ Kein User für SEO-Test")
            return False
        
        print("🔄 Teste SEO-Service...")
        
        # Teste OpenAI Service direkt
        try:
            service = OpenAIService(user=user)
            success, result, message = service.generate_seo(
                "Test Produkt", 
                "Dies ist eine Test-Beschreibung für ein Produkt", 
                ["test", "produkt", "seo"]
            )
            
            print(f"📊 SEO Generation - Success: {success}")
            print(f"📊 SEO Message: {message}")
            
            if success and result:
                print(f"✅ SEO Title: {result.get('seo_title', 'N/A')}")
                print(f"✅ SEO Description: {result.get('seo_description', 'N/A')}")
                return True
            else:
                print(f"❌ SEO-Generierung fehlgeschlagen: {message}")
                return False
                
        except Exception as e:
            print(f"❌ SEO-Service Fehler: {e}")
            return False
            
    except Exception as e:
        print(f"❌ SEO-Test Fehler: {e}")
        return False

if __name__ == '__main__':
    print("Starte OpenAI API-Diagnose...\n")
    
    # Test 1: API-Key Abruf
    key_test = test_api_key_retrieval()
    
    # Test 2: SEO-Generierung (nur wenn API-Key funktioniert)
    if key_test:
        seo_test = test_seo_generation()
        
        if seo_test:
            print("\n🎉 Alle Tests erfolgreich! OpenAI API funktioniert korrekt.")
        else:
            print("\n⚠️ API-Key funktioniert, aber SEO-Generierung hat Probleme.")
    else:
        print("\n❌ API-Key Problem verhindert weitere Tests.")
    
    print("\nDiagnose beendet.")
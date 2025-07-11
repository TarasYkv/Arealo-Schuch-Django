#!/usr/bin/env python3
"""
Test-Script für AI-Modell-Konfigurationen
Überprüft, ob alle Modelle korrekt gemappt sind
"""

import os
import sys
import django

# Django Setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.ai_seo_service import get_ai_service, get_blog_ai_service, MockAIService

def test_ai_models():
    """Testet alle konfigurierten AI-Modelle"""
    
    # Modelle aus der View (sollten alle funktionieren)
    models_to_test = [
        # Claude (Anthropic) Modelle
        'claude-opus-4',
        'claude-sonnet-4', 
        'claude-sonnet-3.7',
        'claude-sonnet-3.5-new',
        'claude-sonnet-3.5',
        'claude-haiku-3.5-new',
        'claude-haiku-3.5',
        
        # OpenAI (ChatGPT) Modelle
        'gpt-4.1',
        'gpt-4.1-mini',
        'gpt-4.1-nano',
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
        'gpt-4',
        'gpt-3.5-turbo',
        
        # OpenAI Reasoning Modelle
        'o3',
        'o4-mini',
        
        # Google Gemini Modelle
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-2.0-pro',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini',
        
        # Test/Mock
        'mock',
    ]
    
    print("🔍 Teste AI-Modell-Konfigurationen...")
    print("=" * 50)
    
    success_count = 0
    mock_count = 0
    error_count = 0
    
    for model_name in models_to_test:
        try:
            # Teste Standard-Service
            service = get_ai_service(model_name)
            service_type = type(service).__name__
            
            # Teste Blog-Service  
            blog_service = get_blog_ai_service(model_name)
            blog_service_type = type(blog_service).__name__
            
            if isinstance(service, MockAIService):
                status = "🟡 MOCK"
                mock_count += 1
            else:
                status = "✅ OK"
                success_count += 1
                
            print(f"{status:8} {model_name:25} → {service_type:20} / {blog_service_type}")
            
        except Exception as e:
            print(f"❌ ERROR  {model_name:25} → {str(e)}")
            error_count += 1
    
    print("=" * 50)
    print(f"📊 Ergebnisse:")
    print(f"   ✅ Funktionierende Modelle: {success_count}")
    print(f"   🟡 Mock-Modelle:           {mock_count}")
    print(f"   ❌ Fehlerhafte Modelle:    {error_count}")
    print(f"   📝 Gesamt getestet:        {len(models_to_test)}")
    
    if error_count == 0:
        print(f"\n🎉 Alle Modelle sind korrekt konfiguriert!")
    else:
        print(f"\n⚠️  {error_count} Modelle haben Konfigurationsfehler.")
    
    return success_count, mock_count, error_count

def test_mock_functionality():
    """Testet die Mock-Funktionalität ohne API-Keys"""
    print(f"\n🧪 Teste Mock-Service Funktionalität...")
    print("=" * 50)
    
    try:
        service = get_ai_service('mock')
        success, result, message = service.generate_seo(
            "Test Produkt", 
            "Eine Beschreibung für ein Test-Produkt", 
            ["test", "produkt", "seo"]
        )
        
        if success:
            print("✅ Mock-Service funktioniert")
            print(f"   SEO-Titel: {result.get('seo_title', 'N/A')}")
            print(f"   SEO-Beschreibung: {result.get('seo_description', 'N/A')}")
            print(f"   Nachricht: {message}")
        else:
            print(f"❌ Mock-Service fehlgeschlagen: {message}")
            
    except Exception as e:
        print(f"❌ Mock-Service Fehler: {e}")

if __name__ == "__main__":
    test_ai_models()
    test_mock_functionality()
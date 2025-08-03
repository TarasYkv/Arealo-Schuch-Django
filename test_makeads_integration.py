#!/usr/bin/env python3
"""
Test script für MakeAds API-Key Integration

Dieses Skript testet die Integration zwischen MakeAds und der zentralen API-Key-Verwaltung.
"""

import os
import sys
import django
from django.conf import settings

# Django Setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth import get_user_model
from makeads.api_client import CentralAPIClient
from makeads.utils import get_available_ai_services, check_api_key_configuration
from django.test import RequestFactory

User = get_user_model()

def test_api_client():
    """Testet den CentralAPIClient"""
    print("🧪 Teste CentralAPIClient...")
    
    # Teste mit dem ersten verfügbaren User
    try:
        user = User.objects.first()
        if not user:
            print("❌ Kein User gefunden - erstelle einen Testuser")
            user = User.objects.create_user(
                username='testuser',
                email='test@example.com',
                password='testpass123'
            )
        
        # Teste API-Client
        api_client = CentralAPIClient(user)
        
        # Teste API-Key Abruf
        keys = api_client.get_api_keys()
        print(f"✅ API-Keys abgerufen: {list(keys.keys())}")
        
        # Teste Validierung
        validation = api_client.validate_api_keys()
        print(f"✅ API-Key Validierung: {validation}")
        
        # Teste einzelne Keys
        openai_key = api_client.get_openai_key()
        anthropic_key = api_client.get_anthropic_key()
        
        print(f"✅ OpenAI Key: {'✓ vorhanden' if openai_key else '✗ nicht konfiguriert'}")
        print(f"✅ Anthropic Key: {'✓ vorhanden' if anthropic_key else '✗ nicht konfiguriert'}")
        
        # Teste Cache
        api_client.clear_cache()
        print("✅ Cache erfolgreich geleert")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Testen des API-Clients: {str(e)}")
        return False

def test_utilities():
    """Testet die Utility-Funktionen"""
    print("\n🧪 Teste Utility-Funktionen...")
    
    try:
        user = User.objects.first()
        if not user:
            print("❌ Kein User für Test verfügbar")
            return False
        
        # Teste verfügbare Services
        services = get_available_ai_services(user)
        print(f"✅ Verfügbare AI-Services: {services}")
        
        # Teste API-Key Konfigurationsprüfung
        factory = RequestFactory()
        request = factory.get('/')
        request.user = user
        
        has_keys = check_api_key_configuration(request, ['openai'])
        print(f"✅ API-Key Konfiguration (OpenAI): {'✓ vorhanden' if has_keys else '✗ fehlt'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Testen der Utilities: {str(e)}")
        return False

def test_middleware_import():
    """Testet ob die Middleware importiert werden kann"""
    print("\n🧪 Teste Middleware Import...")
    
    try:
        from makeads.middleware import APIKeyCacheMiddleware
        middleware = APIKeyCacheMiddleware(lambda x: x)
        print("✅ Middleware erfolgreich importiert und initialisiert")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Importieren der Middleware: {str(e)}")
        return False

def test_decorators():
    """Testet die Decorator-Funktionen"""
    print("\n🧪 Teste Decorators...")
    
    try:
        from makeads.decorators import require_api_keys, optional_api_keys
        
        # Erstelle Test-View
        @require_api_keys(['openai'])
        def test_view(request):
            return "OK"
        
        print("✅ require_api_keys Decorator erfolgreich angewendet")
        
        @optional_api_keys(['openai', 'anthropic'])
        def test_view2(request):
            return "OK"
        
        print("✅ optional_api_keys Decorator erfolgreich angewendet")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Testen der Decorators: {str(e)}")
        return False

def main():
    """Haupttestfunktion"""
    print("🚀 Starte MakeAds API-Key Integration Test\n")
    
    tests = [
        test_api_client,
        test_utilities,
        test_middleware_import,
        test_decorators
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Ergebnisse: {passed}/{total} Tests bestanden")
    
    if passed == total:
        print("🎉 Alle Tests erfolgreich! MakeAds API-Key Integration ist funktionsbereit.")
    else:
        print("⚠️  Einige Tests sind fehlgeschlagen. Bitte prüfen Sie die Konfiguration.")
    
    print(f"\n💡 Nächste Schritte:")
    print(f"   1. Server starten: python manage.py runserver")
    print(f"   2. MakeAds Dashboard aufrufen: http://127.0.0.1:8000/makeads/")
    print(f"   3. API-Keys konfigurieren: http://127.0.0.1:8000/accounts/neue-api-einstellungen/")

if __name__ == "__main__":
    main()
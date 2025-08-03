"""
Debug-Tools für MakeAds API-Key Integration

Diese Tools helfen beim Debugging der API-Key-Konfiguration und der Bildgenerierung.
"""

import logging
from django.contrib.auth import get_user_model
from .api_client import CentralAPIClient
from .ai_service import AICreativeGenerator

logger = logging.getLogger(__name__)
User = get_user_model()


def debug_api_keys(user_id=None):
    """
    Debuggt die API-Key-Konfiguration für einen bestimmten User
    
    Args:
        user_id: User ID (optional, verwendet ersten User wenn nicht angegeben)
    """
    print("🔍 MakeAds API-Key Debug-Analyse")
    print("=" * 50)
    
    try:
        # User laden
        if user_id:
            user = User.objects.get(id=user_id)
        else:
            user = User.objects.first()
            
        if not user:
            print("❌ Kein User gefunden!")
            return
            
        print(f"👤 User: {user.username} (ID: {user.id})")
        print(f"📧 Email: {user.email}")
        print()
        
        # API-Client testen
        print("🔑 API-Key Status:")
        api_client = CentralAPIClient(user)
        
        # Direkte User-Attribute prüfen
        print("📋 Direkte User-Attribute:")
        print(f"  - openai_api_key: {'✓ gesetzt' if user.openai_api_key else '✗ nicht gesetzt'}")
        print(f"  - anthropic_api_key: {'✓ gesetzt' if user.anthropic_api_key else '✗ nicht gesetzt'}")
        print(f"  - google_api_key: {'✓ gesetzt' if user.google_api_key else '✗ nicht gesetzt'}")
        print()
        
        # API-Client Keys prüfen
        print("🔗 Via CentralAPIClient:")
        keys = api_client.get_api_keys()
        for service, key in keys.items():
            status = "✓ verfügbar" if key else "✗ nicht konfiguriert"
            length = f" ({len(key)} Zeichen)" if key else ""
            print(f"  - {service}: {status}{length}")
        print()
        
        # Validierung testen
        print("✅ Validierung:")
        validation = api_client.validate_api_keys()
        for service, valid in validation.items():
            print(f"  - {service}: {'✓ gültig' if valid else '✗ ungültig'}")
        print()
        
        # Service-Verfügbarkeit
        required_services = ['openai']
        has_required = api_client.has_required_keys(required_services)
        print(f"🎯 Erforderliche Services ({', '.join(required_services)}): {'✓ verfügbar' if has_required else '✗ fehlen'}")
        print()
        
        # AI-Generator testen
        print("🤖 AICreativeGenerator Test:")
        ai_generator = AICreativeGenerator(user)
        print(f"  - OpenAI Key geladen: {'✓ ja' if ai_generator.openai_api_key else '✗ nein'}")
        print(f"  - Anthropic Key geladen: {'✓ ja' if ai_generator.anthropic_api_key else '✗ nein'}")
        print(f"  - Google Key geladen: {'✓ ja' if ai_generator.google_api_key else '✗ nein'}")
        
        return {
            'user': user,
            'api_keys': keys,
            'validation': validation,
            'has_required': has_required,
            'ai_generator': ai_generator
        }
        
    except Exception as e:
        print(f"❌ Fehler beim Debugging: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_image_generation(user_id=None, prompt="A modern, professional advertisement for a tech company"):
    """
    Testet die Bildgenerierung mit einem einfachen Prompt
    
    Args:
        user_id: User ID (optional)
        prompt: Test-Prompt für die Bildgenerierung
    """
    print("🖼️  MakeAds Bildgenerierungs-Test")
    print("=" * 50)
    
    debug_result = debug_api_keys(user_id)
    if not debug_result:
        return
    
    user = debug_result['user']
    ai_generator = debug_result['ai_generator']
    
    print(f"🎨 Test-Prompt: {prompt}")
    print()
    
    # Teste Bildgenerierung
    print("🚀 Starte Bildgenerierung...")
    try:
        image_url = ai_generator._generate_image(prompt, 'openai')
        print(f"✅ Bild generiert: {image_url}")
        
        if image_url.startswith('https://via.placeholder.com'):
            print("⚠️  WARNUNG: Mock-Bild wurde verwendet!")
            print("   Mögliche Ursachen:")
            print("   - Kein OpenAI API-Key konfiguriert")
            print("   - API-Key ist ungültig")
            print("   - Netzwerkproblem")
        else:
            print("🎉 Echtes DALL-E Bild wurde generiert!")
            
    except Exception as e:
        print(f"❌ Fehler bei der Bildgenerierung: {str(e)}")
        import traceback
        traceback.print_exc()


def test_text_generation(user_id=None, prompt="Erstelle einen kurzen Werbetext für ein innovatives Tech-Produkt"):
    """
    Testet die Textgenerierung
    
    Args:
        user_id: User ID (optional)
        prompt: Test-Prompt für die Textgenerierung
    """
    print("📝 MakeAds Textgenerierungs-Test")
    print("=" * 50)
    
    debug_result = debug_api_keys(user_id)
    if not debug_result:
        return
    
    user = debug_result['user']
    ai_generator = debug_result['ai_generator']
    
    print(f"📄 Test-Prompt: {prompt}")
    print()
    
    # Teste Textgenerierung
    print("🚀 Starte Textgenerierung...")
    try:
        result = ai_generator._generate_text(prompt, 'openai')
        print("✅ Text generiert:")
        print(f"   Inhalt: {result.get('content', 'N/A')}")
        print(f"   Beschreibung: {result.get('description', 'N/A')}")
        
        # Prüfe ob Mock verwendet wurde
        mock_indicators = ['🚀', '✨', '🎯', '💡', '🌟']
        content = result.get('content', '')
        is_mock = any(indicator in content for indicator in mock_indicators)
        
        if is_mock:
            print("⚠️  WARNUNG: Mock-Text wurde verwendet!")
            print("   Mögliche Ursachen:")
            print("   - Kein OpenAI API-Key konfiguriert")
            print("   - API-Key ist ungültig")
            print("   - Netzwerkproblem")
        else:
            print("🎉 Echter OpenAI Text wurde generiert!")
            
    except Exception as e:
        print(f"❌ Fehler bei der Textgenerierung: {str(e)}")
        import traceback
        traceback.print_exc()


def run_full_debug(user_id=None):
    """
    Führt alle Debug-Tests aus
    """
    print("🚀 Vollständiger MakeAds Debug-Test")
    print("=" * 60)
    
    # API-Keys debuggen
    debug_api_keys(user_id)
    print("\n" + "-" * 60 + "\n")
    
    # Textgenerierung testen
    test_text_generation(user_id)
    print("\n" + "-" * 60 + "\n")
    
    # Bildgenerierung testen
    test_image_generation(user_id)
    print("\n" + "=" * 60)
    
    print("💡 Wenn Mock-Inhalte verwendet werden:")
    print("   1. Gehen Sie zu: http://127.0.0.1:8000/accounts/neue-api-einstellungen/")
    print("   2. Fügen Sie einen gültigen OpenAI API-Key hinzu")
    print("   3. Testen Sie erneut")


if __name__ == "__main__":
    # Kann als Standalone-Skript ausgeführt werden
    import os
    import sys
    import django
    
    # Django Setup
    sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
    django.setup()
    
    run_full_debug()
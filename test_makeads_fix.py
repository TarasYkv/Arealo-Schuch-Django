#!/usr/bin/env python3
"""
Test-Skript für die MakeAds Fehlerbehebung

Testet spezifisch den existing_examples Parameter Fehler
"""

import os
import sys
import django

# Django Setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth import get_user_model
from makeads.models import Campaign
from makeads.ai_service import AICreativeGenerator

User = get_user_model()

def test_generate_more_creatives():
    """Testet die generate_more_creatives Methode die den Fehler verursacht hat"""
    print("🧪 Teste generate_more_creatives Methode...")
    
    try:
        # User laden
        user = User.objects.first()
        if not user:
            print("❌ Kein User gefunden")
            return False
            
        # Kampagne erstellen oder laden
        campaign, created = Campaign.objects.get_or_create(
            user=user,
            name="Test Kampagne",
            defaults={
                'basic_idea': 'Test einer Werbekampagne für Debugging',
                'detailed_description': 'Dies ist eine Test-Kampagne um die generate_more_creatives Funktion zu testen.'
            }
        )
        
        if created:
            print(f"✅ Test-Kampagne erstellt: {campaign.name}")
        else:
            print(f"✅ Verwende existierende Kampagne: {campaign.name}")
        
        # AI Generator erstellen
        ai_generator = AICreativeGenerator(user)
        print(f"✅ AICreativeGenerator für User {user.username} erstellt")
        
        # Teste generate_more_creatives (das sollte jetzt funktionieren)
        print("🚀 Teste generate_more_creatives...")
        
        try:
            creatives = ai_generator.generate_more_creatives(
                campaign=campaign,
                count=2,  # Nur 2 für schnellen Test
                ai_service='openai',
                style_preference='modern',
                color_scheme='vibrant'
            )
            
            print(f"✅ generate_more_creatives erfolgreich! {len(creatives)} Creatives generiert")
            
            for i, creative in enumerate(creatives, 1):
                print(f"   Creative {i}: {creative.title}")
                print(f"   Status: {creative.generation_status}")
                if creative.image_url:
                    if 'placeholder.com' in creative.image_url:
                        print(f"   Bild: Mock-Bild (kein API-Key)")
                    else:
                        print(f"   Bild: Echtes DALL-E Bild ✨")
                        
            return True
            
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                print(f"❌ Fehler noch nicht behoben: {str(e)}")
                return False
            else:
                print(f"❌ Anderer TypeError: {str(e)}")
                return False
                
    except Exception as e:
        print(f"❌ Allgemeiner Fehler: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_generate_creatives_with_examples():
    """Testet die generate_creatives Methode mit existing_examples Parameter"""
    print("\n🧪 Teste generate_creatives mit existing_examples...")
    
    try:
        user = User.objects.first()
        if not user:
            print("❌ Kein User gefunden")
            return False
            
        campaign = Campaign.objects.filter(user=user).first()
        if not campaign:
            print("❌ Keine Kampagne gefunden")
            return False
            
        ai_generator = AICreativeGenerator(user)
        
        # Test mit existing_examples Parameter
        existing_examples = [
            {
                'title': 'Beispiel Creative 1',
                'text': 'Revolutioniere dein Business mit unserer innovativen Lösung!',
                'description': 'Modernes Tech-Creative'
            }
        ]
        
        creatives = ai_generator.generate_creatives(
            campaign=campaign,
            count=1,
            ai_service='openai',
            style_preference='modern',
            color_scheme='vibrant',
            existing_examples=existing_examples
        )
        
        print(f"✅ generate_creatives mit existing_examples erfolgreich! {len(creatives)} Creative generiert")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Testen mit existing_examples: {str(e)}")
        return False

def main():
    """Haupttest-Funktion"""
    print("🚀 MakeAds Parameter-Fehler Fix Test")
    print("=" * 50)
    
    # Test 1: generate_more_creatives
    success1 = test_generate_more_creatives()
    
    # Test 2: generate_creatives mit existing_examples
    success2 = test_generate_creatives_with_examples()
    
    print("\n📊 Test-Ergebnisse:")
    print(f"   generate_more_creatives: {'✅ OK' if success1 else '❌ FEHLER'}")
    print(f"   generate_creatives mit examples: {'✅ OK' if success2 else '❌ FEHLER'}")
    
    if success1 and success2:
        print("\n🎉 Alle Tests erfolgreich! Der existing_examples Fehler ist behoben.")
    else:
        print("\n⚠️  Einige Tests sind fehlgeschlagen. Weitere Anpassungen nötig.")

if __name__ == "__main__":
    main()
"""
Schnelle Behebung des MakeAds Parameter-Fehlers

Dieser Fehler trat auf: "AICreativeGenerator.generate_creatives() got an unexpected keyword argument 'existing_examples'"
"""

print("🔧 MakeAds Parameter-Fehler Fix")
print("=" * 40)

print("✅ Problem identifiziert:")
print("   - generate_more_creatives() übergibt 'existing_examples' Parameter")
print("   - generate_creatives() erwartet diesen Parameter nicht")
print()

print("✅ Lösung implementiert:")
print("   1. existing_examples Parameter zu generate_creatives() hinzugefügt")
print("   2. Parameter korrekt an _build_text_prompt() weitergegeben")
print("   3. generate_more_creatives() repariert für explizite Parameterübergabe")
print()

print("📁 Geänderte Dateien:")
print("   - makeads/ai_service.py")
print("     * generate_creatives(): existing_examples=None Parameter hinzugefügt")
print("     * _build_text_prompt(): Aufruf mit existing_examples aktualisiert")
print("     * generate_more_creatives(): Explizite Parameterübergabe")
print()

print("🧪 Test-Befehl (in Django-Shell):")
print("   python manage.py shell")
print("   >>> from django.contrib.auth import get_user_model")
print("   >>> from makeads.models import Campaign")
print("   >>> from makeads.ai_service import AICreativeGenerator")
print("   >>> User = get_user_model()")
print("   >>> user = User.objects.first()")
print("   >>> campaign = Campaign.objects.filter(user=user).first()")
print("   >>> generator = AICreativeGenerator(user)")
print("   >>> creatives = generator.generate_more_creatives(campaign, count=1)")
print("   >>> print(f'Erfolgreich: {len(creatives)} Creatives generiert')")
print()

print("🎯 Erwartetes Ergebnis:")
print("   - Kein 'unexpected keyword argument' Fehler mehr")
print("   - generate_more_creatives() funktioniert korrekt")
print("   - Creatives werden generiert (Mock oder echt, je nach API-Key)")
print()

print("💡 Nächste Schritte:")
print("   1. Server neu starten: python manage.py runserver")
print("   2. MakeAds öffnen und 'Weitere Creatives generieren' testen")
print("   3. Bei weiteren Problemen: python manage.py debug_makeads")
print()

print("🎉 Fix ist implementiert und bereit zum Testen!")

# Zeige die wichtigsten Änderungen
print("\n📝 Code-Änderungen im Detail:")
print("-" * 40)

print("VORHER (fehlerhaft):")
print("""
def generate_creatives(self, campaign, count=10, ai_service='openai', ...):
    # existing_examples Parameter fehlt!

def generate_more_creatives(self, campaign, count=5, **kwargs):
    return self.generate_creatives(campaign, count, **kwargs)
    # Übergibt existing_examples, aber generate_creatives erwartet es nicht!
""")

print("NACHHER (funktioniert):")
print("""
def generate_creatives(self, campaign, count=10, ai_service='openai', ..., existing_examples=None):
    # existing_examples Parameter hinzugefügt ✅

def generate_more_creatives(self, campaign, count=5, **kwargs):
    return self.generate_creatives(
        campaign=campaign, 
        count=count, 
        existing_examples=kwargs.get('existing_examples'),
        **{k: v for k, v in kwargs.items() if k != 'existing_examples'}
    )
    # Explizite Parameterübergabe ✅
""")

print("\n✅ Der Fehler ist behoben!")
print("Jetzt sollte 'Weitere Creatives generieren' funktionieren.")
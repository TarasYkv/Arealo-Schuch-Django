#!/usr/bin/env python3
"""
Test-Script für DeepSeek Integration in BlogPrep
Führe aus mit: python manage.py shell < test_deepseek.py
"""
import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from blogprep.ai_services.content_service import ContentService
from blogprep.models import BlogPrepSettings

User = get_user_model()

# Ersten User mit DeepSeek API Key finden
user = User.objects.filter(deepseek_api_key__isnull=False).exclude(deepseek_api_key='').first()

if not user:
    print("❌ Kein User mit DeepSeek API Key gefunden!")
    print("   Bitte DeepSeek API Key in den Account-Einstellungen hinterlegen.")
    sys.exit(1)

print(f"✅ User gefunden: {user.username}")
print(f"   DeepSeek Key: {user.deepseek_api_key[:10]}...")

# Settings erstellen/laden
settings, created = BlogPrepSettings.objects.get_or_create(user=user)
settings.ai_provider = 'deepseek'
settings.ai_model = 'deepseek-chat'
settings.save()

print(f"   Provider: {settings.ai_provider}")
print(f"   Model: {settings.ai_model}")

# ContentService initialisieren
print("\n🔄 Teste DeepSeek API...")
service = ContentService(user, settings)

# Einfacher Test-Call
result = service._call_llm(
    system_prompt="Du bist ein hilfreicher Assistent.",
    user_prompt="Sage 'DeepSeek funktioniert!' und nichts anderes.",
    max_tokens=50,
    temperature=0.1
)

if result['success']:
    print(f"\n✅ ERFOLG!")
    print(f"   Antwort: {result['content']}")
    print(f"   Input Tokens: {result.get('tokens_input', 'N/A')}")
    print(f"   Output Tokens: {result.get('tokens_output', 'N/A')}")
    print(f"   Dauer: {result.get('duration', 0):.2f}s")
else:
    print(f"\n❌ FEHLER: {result['error']}")

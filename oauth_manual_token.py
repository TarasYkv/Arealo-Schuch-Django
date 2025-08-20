#!/usr/bin/env python3
"""
Manueller OAuth Token Setup
Für den Fall, dass der automatische Flow nicht funktioniert
"""

import os
import sys
import django
from pathlib import Path

# Django Setup
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arealo_schuch.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import ZohoAPISettings
from mail_app.models import EmailAccount
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def manual_token_setup():
    """Manueller Token-Setup falls OAuth Flow nicht funktioniert"""
    
    print("=" * 60)
    print("🔧 MANUELLER OAUTH TOKEN SETUP")
    print("=" * 60)
    
    user = User.objects.first()
    if not user:
        print("❌ Kein User gefunden")
        return
    
    print("Dieser Modus ist für den Fall, dass Zoho Console erreichbar ist")
    print("und du dort einen Access Token generieren kannst.\n")
    
    print("📋 SCHRITTE:")
    print("1. Gehe zu Zoho Console (falls erreichbar)")
    print("2. Self Client → Generate Token")
    print("3. Scopes: ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ,ZohoMail.messages.CREATE")
    print("4. Access Token kopieren")
    print("5. Hier eingeben\n")
    
    # Zoho Settings laden
    try:
        settings = ZohoAPISettings.objects.get(user=user)
        print(f"✅ ZohoAPISettings gefunden")
        print(f"Region: {settings.region}")
        print(f"Client ID: {settings.client_id[:10]}...")
    except:
        print("❌ ZohoAPISettings nicht gefunden")
        return
    
    # Manuellen Token eingeben
    print("\n" + "─" * 50)
    manual_token = input("📝 Access Token eingeben (oder Enter für Abbruch): ").strip()
    
    if not manual_token:
        print("❌ Abgebrochen")
        return
    
    if len(manual_token) < 50:
        print("❌ Token zu kurz - vermutlich ungültig")
        return
    
    # Email eingeben
    email_address = input("📧 Email Adresse eingeben: ").strip()
    if not email_address or '@' not in email_address:
        email_address = "kontakt@workloom.de"  # Fallback
        print(f"📧 Verwende Fallback: {email_address}")
    
    try:
        # Alte Accounts löschen
        EmailAccount.objects.filter(user=user).delete()
        
        # ZohoAPISettings aktualisieren
        settings.access_token = manual_token
        settings.refresh_token = ""  # Kein Refresh Token bei manueller Eingabe
        settings.token_expires_at = timezone.now() + timedelta(hours=1)  # 1 Stunde
        settings.is_active = True
        settings.save()
        
        # EmailAccount erstellen
        account = EmailAccount.objects.create(
            user=user,
            email_address=email_address,
            display_name=email_address,
            access_token=manual_token,
            refresh_token="",  # Kein Refresh Token
            token_expires_at=timezone.now() + timedelta(hours=1),
            is_default=True,
            sync_enabled=True,
            is_active=True
        )
        
        print(f"\n✅ ERFOLGREICH ERSTELLT!")
        print(f"📧 Email Account: {account.email_address}")
        print(f"⏰ Token gültig bis: {account.token_expires_at}")
        print(f"\n⚠️  HINWEIS: Manueller Token hat kurze Gültigkeit")
        print(f"Nach Ablauf muss OAuth Flow funktionieren für automatische Erneuerung")
        
    except Exception as e:
        print(f"❌ Fehler beim Erstellen: {e}")

def show_current_status():
    """Zeigt aktuellen Status"""
    user = User.objects.first()
    accounts = EmailAccount.objects.filter(user=user)
    
    print("\n" + "=" * 40)
    print("📊 AKTUELLER STATUS")
    print("=" * 40)
    
    if accounts.exists():
        for account in accounts:
            print(f"✅ {account.email_address}")
            print(f"   Token: {'✅ Vorhanden' if account.access_token else '❌ Fehlt'}")
            print(f"   Gültig bis: {account.token_expires_at}")
            print(f"   Status: {account.status}")
    else:
        print("❌ Keine Email Accounts")

if __name__ == "__main__":
    show_current_status()
    
    choice = input("\n🔧 Manueller Token Setup starten? (y/N): ").strip().lower()
    if choice in ['y', 'yes', 'ja']:
        manual_token_setup()
        show_current_status()
    else:
        print("👋 Setup abgebrochen")
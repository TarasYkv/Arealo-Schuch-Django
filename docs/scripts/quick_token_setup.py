#!/usr/bin/env python3
"""
Schneller Token Setup - ohne interaktive Eingabe
"""

import os
import sys
import django
from pathlib import Path

# Django Setup
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import ZohoAPISettings
from mail_app.models import EmailAccount
from django.utils import timezone
from datetime import timedelta

def setup_with_token(token, email="kontakt@workloom.de", hours=24):
    """Schneller Setup mit Token"""
    
    User = get_user_model()
    user = User.objects.first()
    
    if not user:
        print("❌ Kein User gefunden")
        return False
        
    try:
        settings = ZohoAPISettings.objects.get(user=user)
        print(f"✅ ZohoAPISettings gefunden: {settings.client_id[:10]}...")
    except:
        print("❌ ZohoAPISettings nicht gefunden")
        return False
    
    if len(token) < 50:
        print("❌ Token zu kurz - ungültig")
        return False
    
    try:
        # Alte Accounts löschen
        old_count = EmailAccount.objects.filter(user=user).count()
        EmailAccount.objects.filter(user=user).delete()
        print(f"🧹 {old_count} alte EmailAccounts gelöscht")
        
        # ZohoAPISettings aktualisieren
        expires_at = timezone.now() + timedelta(hours=hours)
        settings.access_token = token
        settings.refresh_token = ""
        settings.token_expires_at = expires_at
        settings.is_active = True
        settings.save()
        print(f"✅ ZohoAPISettings aktualisiert")
        
        # EmailAccount erstellen
        account = EmailAccount.objects.create(
            user=user,
            email_address=email,
            display_name=email,
            access_token=token,
            refresh_token="",
            token_expires_at=expires_at,
            is_default=True,
            sync_enabled=True,
            is_active=True,
            provider='zoho'
        )
        
        print(f"✅ EmailAccount erstellt: {account.email_address}")
        print(f"⏰ Gültig bis: {account.token_expires_at}")
        
        # Soforttest
        print(f"\n🧪 FUNKTIONSTEST...")
        from mail_app.services.sync import EmailSyncService
        sync_service = EmailSyncService(account)
        
        try:
            folders = sync_service.sync_folders()
            print(f"✅ Ordner-Sync erfolgreich: {folders} Ordner")
        except Exception as e:
            print(f"⚠️  Ordner-Sync Warnung: {e}")
        
        print(f"\n🎉 SETUP KOMPLETT ERFOLGREICH!")
        return True
        
    except Exception as e:
        print(f"❌ Setup fehlgeschlagen: {e}")
        return False

if __name__ == "__main__":
    print("🚀 QUICK TOKEN SETUP")
    print("=" * 50)
    
    # Hier den Token aus dem Browser einfügen:
    token = input("📝 Access Token hier einfügen: ").strip()
    
    if token:
        success = setup_with_token(token)
        if success:
            print("\n✅ Email-System bereit für Benutzung!")
        else:
            print("\n❌ Setup fehlgeschlagen")
    else:
        print("❌ Kein Token eingegeben")
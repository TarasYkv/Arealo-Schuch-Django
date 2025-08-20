#!/usr/bin/env python3
"""
Self-Client Token Generator für Zoho
Umgeht das Authorization Code Timing Problem komplett
"""

import os
import sys
import django
from pathlib import Path

# Django Setup
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

import requests
import webbrowser
from django.contrib.auth import get_user_model
from accounts.models import ZohoAPISettings
from mail_app.models import EmailAccount
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def generate_self_client_url():
    """Generiert Self-Client URL für direkten Token ohne Authorization Code"""
    
    print("=" * 60)
    print("🔐 SELF-CLIENT TOKEN GENERATOR")
    print("=" * 60)
    
    user = User.objects.first()
    if not user:
        print("❌ Kein User gefunden")
        return
    
    try:
        settings = ZohoAPISettings.objects.get(user=user)
        print(f"✅ ZohoAPISettings gefunden")
        print(f"Region: {settings.region}")
        print(f"Client ID: {settings.client_id}")
    except Exception as e:
        print(f"❌ ZohoAPISettings nicht gefunden: {e}")
        return
    
    # Self-Client Token URL generieren
    scopes = "ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ,ZohoMail.messages.CREATE"
    
    # Self-Client URLs für verschiedene Regionen
    self_client_urls = {
        'EU': f"https://accounts.zoho.eu/developerconsole/home#{settings.client_id}/selfclient",
        'US': f"https://accounts.zoho.com/developerconsole/home#{settings.client_id}/selfclient", 
        'IN': f"https://accounts.zoho.in/developerconsole/home#{settings.client_id}/selfclient",
        'AU': f"https://accounts.zoho.com.au/developerconsole/home#{settings.client_id}/selfclient"
    }
    
    region = settings.region or 'EU'
    self_client_url = self_client_urls.get(region, self_client_urls['EU'])
    
    print(f"\n🌐 SELBST-CLIENT SETUP:")
    print(f"Region: {region}")
    print(f"Client ID: {settings.client_id}")
    print(f"Scopes: {scopes}")
    print(f"\n📋 ANLEITUNG:")
    print(f"1. Browser öffnet Self-Client Seite")
    print(f"2. Scopes eingeben: {scopes}")
    print(f"3. 'Generate' klicken")
    print(f"4. Access Token kopieren")
    print(f"5. Hier einfügen")
    
    # Browser öffnen
    print(f"\n🌐 Öffne Self-Client Seite...")
    try:
        webbrowser.open(self_client_url)
        print(f"✅ Browser geöffnet: {self_client_url}")
    except Exception as e:
        print(f"⚠️  Browser konnte nicht geöffnet werden: {e}")
        print(f"📋 Kopiere diese URL manuell: {self_client_url}")
    
    print(f"\n" + "─" * 60)
    print(f"📝 SCOPES KOPIEREN UND EINFÜGEN:")
    print(f"{scopes}")
    print(f"─" * 60)
    
    # Token eingeben
    print(f"\n⏳ Warte auf Token-Eingabe...")
    access_token = input("📝 Access Token hier einfügen (oder Enter für Abbruch): ").strip()
    
    if not access_token:
        print("❌ Abgebrochen")
        return
    
    if len(access_token) < 50:
        print("❌ Token zu kurz - vermutlich ungültig")
        return
    
    # Zusätzliche Token-Details
    duration_hours = input("⏰ Token-Gültigkeit in Stunden (1-720, Enter für 24): ").strip()
    try:
        duration_hours = int(duration_hours) if duration_hours else 24
        duration_hours = max(1, min(720, duration_hours))  # 1-720 Stunden
    except:
        duration_hours = 24
    
    email_address = input("📧 Email Adresse (Enter für kontakt@workloom.de): ").strip()
    if not email_address or '@' not in email_address:
        email_address = "kontakt@workloom.de"
    
    # Token testen
    print(f"\n🧪 Teste Token...")
    if test_token(access_token, settings):
        setup_account_with_token(user, settings, access_token, email_address, duration_hours)
    else:
        print(f"❌ Token ungültig - bitte nochmal versuchen")

def test_token(token, settings):
    """Testet ob Token funktioniert"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        # Teste verschiedene Endpoints
        test_urls = [
            f"{settings.base_url}/accounts",
            f"{settings.base_url}/me/accounts", 
            f"{settings.base_url}/accounts/self"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    print(f"✅ Token funktioniert mit {url}")
                    return True
            except:
                continue
        
        print(f"❌ Token funktioniert mit keinem Endpoint")
        return False
        
    except Exception as e:
        print(f"❌ Token-Test fehlgeschlagen: {e}")
        return False

def setup_account_with_token(user, settings, token, email, hours):
    """Richtet Account mit Self-Client Token ein"""
    try:
        # Alte Accounts löschen
        EmailAccount.objects.filter(user=user).delete()
        print(f"🧹 Alte EmailAccounts gelöscht")
        
        # ZohoAPISettings aktualisieren
        expires_at = timezone.now() + timedelta(hours=hours)
        settings.access_token = token
        settings.refresh_token = ""  # Self-Client hat keinen Refresh Token
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
            refresh_token="",  # Self-Client Token
            token_expires_at=expires_at,
            is_default=True,
            sync_enabled=True,
            is_active=True,
            provider='zoho'
        )
        print(f"✅ EmailAccount erstellt")
        
        print(f"\n🎉 SETUP ERFOLGREICH!")
        print(f"📧 Email: {account.email_address}")
        print(f"⏰ Gültig bis: {account.token_expires_at}")
        print(f"🔄 Sync aktiviert: {account.sync_enabled}")
        
        # Sofort testen
        print(f"\n🧪 FUNKTIONSTEST...")
        test_sync(account)
        
    except Exception as e:
        print(f"❌ Setup fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()

def test_sync(account):
    """Testet Email-Sync sofort"""
    try:
        from mail_app.services.sync import EmailSyncService
        
        sync_service = EmailSyncService(account)
        folders_synced = sync_service.sync_folders()
        
        if folders_synced > 0:
            print(f"✅ Ordner-Sync erfolgreich: {folders_synced} Ordner")
        else:
            print(f"⚠️  Ordner-Sync: 0 Ordner (möglicherweise OK)")
            
    except Exception as e:
        print(f"⚠️  Sync-Test fehlgeschlagen: {e}")
        print(f"Account wurde trotzdem erstellt - Sync später möglich")

if __name__ == "__main__":
    print("🚀 Self-Client Token Generator")
    print("Umgeht Authorization Code Timing-Probleme komplett\n")
    
    generate_self_client_url()
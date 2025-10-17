#!/usr/bin/env python3
"""
Automatisches OAuth Retry System
Führt OAuth-Flow mit mehreren Versuchen aus um Timing-Probleme zu umgehen
"""

import os
import sys
import django
from pathlib import Path

# Django Setup
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arealo_schuch.settings')
django.setup()

import time
import webbrowser
from django.contrib.auth import get_user_model
from mail_app.services.oauth import ZohoOAuthService
from accounts.models import ZohoAPISettings
from mail_app.models import EmailAccount

User = get_user_model()

def auto_oauth_flow():
    """Automatischer OAuth Flow mit Retry-Logik"""
    
    print("=" * 60)
    print("🔄 AUTOMATISCHER OAUTH RETRY SYSTEM")
    print("=" * 60)
    
    user = User.objects.first()
    if not user:
        print("❌ Kein User gefunden")
        return False
    
    # Alte Accounts löschen
    EmailAccount.objects.filter(user=user).delete()
    print("🧹 Alte EmailAccounts gelöscht")
    
    # OAuth Service initialisieren
    oauth_service = ZohoOAuthService(user=user)
    
    for attempt in range(1, 4):  # 3 Versuche
        print(f"\n🔄 VERSUCH {attempt}/3")
        print("-" * 40)
        
        try:
            # State für CSRF-Schutz
            state = f"user_{user.id}_attempt_{attempt}"
            
            # Erweiterte Authorization URL generieren
            auth_url = oauth_service.get_authorization_url(
                state=state, 
                force_refresh=True
            )
            
            print(f"✅ Authorization URL generiert")
            print(f"🌐 Öffne Browser für OAuth...")
            
            # Browser öffnen
            webbrowser.open(auth_url)
            
            print(f"\n⏰ WICHTIG: Du hast 5 MINUTEN Zeit!")
            print(f"1. Im Browser: Zoho Login durchführen")
            print(f"2. 'Allow' klicken")
            print(f"3. Warten auf Redirect")
            print(f"\nNach dem Redirect wird automatisch versucht...")
            
            # Warten auf User-Interaktion
            for wait_time in range(300, 0, -30):  # 5 Minuten, alle 30 Sekunden checken
                print(f"\r⏱️  Warte auf OAuth Callback... ({wait_time}s verbleibend)", end="", flush=True)
                time.sleep(30)
                
                # Prüfen ob EmailAccount erstellt wurde (erfolgreicher OAuth)
                if EmailAccount.objects.filter(user=user).exists():
                    print(f"\n✅ OAuth erfolgreich! EmailAccount wurde erstellt.")
                    return True
            
            print(f"\n⏰ Zeit abgelaufen für Versuch {attempt}")
            
        except Exception as e:
            print(f"❌ Fehler bei Versuch {attempt}: {e}")
        
        if attempt < 3:
            print(f"⏳ Warte 2 Minuten vor nächstem Versuch...")
            time.sleep(120)  # 2 Minuten warten
    
    print(f"\n❌ Alle Versuche fehlgeschlagen")
    return False

def check_oauth_status():
    """Prüft aktuellen OAuth Status"""
    user = User.objects.first()
    accounts = EmailAccount.objects.filter(user=user)
    
    print("\n" + "=" * 40)
    print("📊 OAUTH STATUS CHECK")
    print("=" * 40)
    
    if accounts.exists():
        for account in accounts:
            print(f"✅ Email Account: {account.email_address}")
            print(f"   Status: {account.status}")
            print(f"   Token: {'✅' if account.access_token else '❌'}")
            print(f"   Expires: {account.token_expires_at}")
        return True
    else:
        print("❌ Keine EmailAccounts gefunden")
        return False

if __name__ == "__main__":
    print("🚀 OAuth Auto-Retry System gestartet\n")
    
    # Status prüfen
    if check_oauth_status():
        print("✅ OAuth bereits erfolgreich - keine Aktion nötig")
    else:
        print("🔄 Starte automatischen OAuth Flow...")
        success = auto_oauth_flow()
        
        if success:
            print("\n🎉 OAUTH ERFOLGREICH!")
            check_oauth_status()
        else:
            print("\n😞 OAuth fehlgeschlagen - manuelle Problemlösung erforderlich")
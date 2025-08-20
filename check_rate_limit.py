#!/usr/bin/env python3
"""
Zoho Rate Limit Checker
"""

import os
import sys
import django
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

import requests
import time
from datetime import datetime
from accounts.models import ZohoAPISettings
from django.contrib.auth import get_user_model

def check_rate_limit():
    """Prüft ob Rate Limit noch aktiv ist"""
    
    User = get_user_model()
    user = User.objects.first()
    
    try:
        settings = ZohoAPISettings.objects.get(user=user)
        print(f"🔍 Rate Limit Check - {datetime.now().strftime('%H:%M:%S')}")
        print(f"Region: {settings.region}")
        
        # Test mit einfachem Authorization URL Check
        test_url = f"{settings.auth_url}?response_type=code&client_id={settings.client_id}&redirect_uri={settings.redirect_uri}&scope=test"
        
        try:
            response = requests.head(test_url, timeout=5)
            
            if response.status_code == 200:
                print("✅ Rate Limit aufgehoben - OAuth wieder möglich!")
                return True
            elif response.status_code == 429:
                print("🚨 Rate Limit noch aktiv (429)")
                return False
            else:
                print(f"⚠️  Unbekannter Status: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            if "throttles_limit_exceeded" in str(e) or "Z101" in str(e):
                print("🚨 Rate Limit noch aktiv (Z101)")
                return False
            else:
                print(f"⚠️  Netzwerk-Fehler: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Fehler beim Check: {e}")
        return False

def monitor_rate_limit():
    """Überwacht Rate Limit alle 5 Minuten"""
    
    print("🔄 RATE LIMIT MONITOR GESTARTET")
    print("Prüft alle 5 Minuten ob Zoho wieder bereit ist")
    print("Drücke Ctrl+C zum Stoppen\n")
    
    try:
        while True:
            if check_rate_limit():
                print("\n🎉 RATE LIMIT AUFGEHOBEN!")
                print("Du kannst jetzt Self-Client Token versuchen:")
                print("python quick_token_setup.py")
                break
            
            print("⏳ Warte 5 Minuten...")
            time.sleep(300)  # 5 Minuten
            
    except KeyboardInterrupt:
        print("\n👋 Monitor gestoppt")

if __name__ == "__main__":
    
    # Einmaliger Check
    result = check_rate_limit()
    
    if not result:
        print("\n🔄 Möchtest du kontinuierlich überwachen?")
        choice = input("Monitor starten? (y/N): ").strip().lower()
        
        if choice in ['y', 'yes', 'ja']:
            monitor_rate_limit()
        else:
            print("\n⏰ Rate Limit noch aktiv")
            print("Versuche es in 30-60 Minuten nochmal")
    else:
        print("\n🚀 Du kannst jetzt OAuth versuchen!")
#!/usr/bin/env python
"""
SQLite-Optimierung für bessere Import-Performance
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Arealo_Schuch.settings')
django.setup()

from django.db import connection

def optimize_sqlite():
    print("=== SQLite OPTIMIERUNG ===")
    
    with connection.cursor() as cursor:
        # Prüfe aktuellen Journal-Modus
        cursor.execute("PRAGMA journal_mode;")
        current_mode = cursor.fetchone()[0]
        print(f"Aktueller Journal-Modus: {current_mode}")
        
        # Setze WAL-Modus für bessere Concurrency
        if current_mode != 'wal':
            print("Setze WAL-Modus...")
            cursor.execute("PRAGMA journal_mode=WAL;")
            new_mode = cursor.fetchone()[0]
            print(f"Neuer Journal-Modus: {new_mode}")
        
        # Optimiere weitere SQLite-Einstellungen
        print("Optimiere SQLite-Einstellungen...")
        
        # Synchronous-Modus reduzieren für bessere Performance
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        # Cache-Größe erhöhen
        cursor.execute("PRAGMA cache_size=10000;")
        
        # Temp-Store im Memory
        cursor.execute("PRAGMA temp_store=MEMORY;")
        
        # Busy-Timeout erhöhen
        cursor.execute("PRAGMA busy_timeout=30000;")
        
        print("✅ SQLite-Optimierung abgeschlossen!")
        
        # Zeige finale Einstellungen
        settings = [
            "journal_mode", "synchronous", "cache_size", 
            "temp_store", "busy_timeout"
        ]
        
        print("\n=== FINALE EINSTELLUNGEN ===")
        for setting in settings:
            cursor.execute(f"PRAGMA {setting};")
            value = cursor.fetchone()[0]
            print(f"{setting}: {value}")

if __name__ == "__main__":
    optimize_sqlite()
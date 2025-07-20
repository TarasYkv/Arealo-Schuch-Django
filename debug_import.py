#!/usr/bin/env python
"""
Debug-Tool für Shopify Import-Probleme
Analysiert die letzten Import-Logs und gibt Hinweise auf häufige Fehlerquellen
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Arealo_Schuch.settings')
django.setup()

import json
from shopify_manager.models import ShopifySyncLog, ShopifyProduct

def analyze_import_errors():
    print("=== SHOPIFY IMPORT FEHLER-ANALYSE ===\n")
    
    # Hole die letzten Import-Logs
    recent_logs = ShopifySyncLog.objects.filter(
        action='import',
        products_failed__gt=0
    ).order_by('-started_at')[:5]
    
    if not recent_logs:
        print("✅ Keine fehlerhaften Imports in den letzten Logs gefunden!")
        return
    
    for i, log in enumerate(recent_logs, 1):
        print(f"--- Import #{i} vom {log.started_at} ---")
        print(f"Status: {log.status}")
        print(f"Verarbeitet: {log.products_processed}")
        print(f"Erfolgreich: {log.products_success}")
        print(f"Fehlgeschlagen: {log.products_failed}")
        print(f"Fehlerrate: {(log.products_failed / log.products_processed * 100):.1f}%")
        
        if log.details:
            try:
                details = json.loads(log.details)
                if 'error_summary' in details:
                    print("\nFehler-Kategorien:")
                    for error_type, info in details['error_summary'].items():
                        print(f"  {error_type}: {info['count']} Fehler")
                        for example in info.get('examples', []):
                            print(f"    → Produkt {example['product_id']}: {example['error_message']}")
            except Exception as e:
                print(f"Fehler beim Lesen der Details: {e}")
        
        if log.error_message:
            print(f"Allgemeine Fehlermeldung: {log.error_message}")
        
        print("-" * 50)
    
    # Produktstatistiken
    print("\n=== PRODUKT-STATISTIKEN ===")
    total_products = ShopifyProduct.objects.count()
    print(f"Aktuell importierte Produkte: {total_products}")
    
    # Finde Produkte mit Problemen
    problematic = ShopifyProduct.objects.filter(
        models.Q(title__isnull=True) | 
        models.Q(title='') |
        models.Q(shopify_id__isnull=True)
    ).count()
    
    if problematic > 0:
        print(f"⚠️  Produkte mit Datenproblemen: {problematic}")
    else:
        print("✅ Keine offensichtlichen Datenprobleme gefunden")

def common_solutions():
    print("\n=== HÄUFIGE LÖSUNGSANSÄTZE ===")
    print("1. **DataError (zu lange Strings)**:")
    print("   → Shopify-Daten überschreiten Django-Feldlängen")
    print("   → Lösung: Automatische Kürzung wurde implementiert")
    print()
    print("2. **IntegrityError (doppelte Einträge)**:")
    print("   → Produkt-IDs kollidieren")
    print("   → Lösung: Verwenden Sie 'Alle löschen und erste 250 importieren'")
    print()
    print("3. **ValidationError (Ungültige Daten)**:")
    print("   → Django-Model-Validierung schlägt fehl")
    print("   → Lösung: Robustere Datenvalidierung wurde implementiert")
    print()
    print("4. **ValueError (Preiskonvertierung)**:")
    print("   → Ungültige Preisformate von Shopify")
    print("   → Lösung: Verbesserte Preis-Parsing-Logik wurde implementiert")
    print()
    print("5. **KeyError (Fehlende Felder)**:")
    print("   → Shopify-API liefert unerwartete Datenstruktur")
    print("   → Lösung: Sichere Feldextraktion mit Fallbacks wurde implementiert")

if __name__ == "__main__":
    from django.db import models
    analyze_import_errors()
    common_solutions()
#!/usr/bin/env python
"""
Test-Skript für Collections-Import
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.models import ShopifyStore, ShopifyCollection
from shopify_manager.shopify_api import ShopifyCollectionSync

def test_collections_import():
    """Testet den Collections-Import"""
    
    # Hole den ersten aktiven Store
    store = ShopifyStore.objects.filter(is_active=True).first()
    if not store:
        print("❌ Kein aktiver Store gefunden")
        return
    
    print(f"🏪 Verwende Store: {store.name} ({store.shop_domain})")
    
    # Teste API-Verbindung
    print("\n1. Teste API-Verbindung...")
    collection_sync = ShopifyCollectionSync(store)
    success, message = collection_sync.api.test_connection()
    
    if not success:
        print(f"❌ API-Verbindung fehlgeschlagen: {message}")
        return
    
    print(f"✅ API-Verbindung erfolgreich: {message}")
    
    # Zeige aktuelle Collections
    print(f"\n2. Aktuelle Collections in der Datenbank:")
    current_collections = ShopifyCollection.objects.filter(store=store)
    print(f"   Anzahl: {current_collections.count()}")
    for collection in current_collections[:5]:  # Zeige erste 5
        print(f"   - {collection.title} (ID: {collection.shopify_id})")
    
    # Teste Collections-Import
    print(f"\n3. Importiere Collections...")
    try:
        sync_log = collection_sync.import_collections(
            import_mode='all',
            overwrite_existing=True
        )
        
        if sync_log.status == 'success':
            print(f"✅ Import erfolgreich!")
            print(f"   Verarbeitet: {sync_log.products_processed}")
            print(f"   Erfolgreich: {sync_log.products_success}")
            print(f"   Fehlgeschlagen: {sync_log.products_failed}")
        else:
            print(f"❌ Import fehlgeschlagen: {sync_log.error_message}")
            
    except Exception as e:
        print(f"❌ Fehler beim Import: {str(e)}")
        return
    
    # Zeige neue Collections
    print(f"\n4. Collections nach Import:")
    new_collections = ShopifyCollection.objects.filter(store=store)
    print(f"   Anzahl: {new_collections.count()}")
    for collection in new_collections[:10]:  # Zeige erste 10
        seo_status = collection.get_combined_seo_status()
        seo_emoji = {'good': '✅', 'warning': '⚠️', 'poor': '❌'}.get(seo_status, '❓')
        print(f"   - {collection.title} {seo_emoji} (SEO: {seo_status})")
    
    # Zeige SEO-Statistiken
    print(f"\n5. SEO-Statistiken:")
    good_seo = new_collections.filter(seo_title__isnull=False, seo_description__isnull=False).count()
    no_seo_title = new_collections.filter(seo_title='').count()
    no_seo_desc = new_collections.filter(seo_description='').count()
    
    print(f"   ✅ Mit SEO-Daten: {good_seo}")
    print(f"   ❌ Ohne SEO-Titel: {no_seo_title}")
    print(f"   ❌ Ohne SEO-Beschreibung: {no_seo_desc}")

if __name__ == "__main__":
    test_collections_import()
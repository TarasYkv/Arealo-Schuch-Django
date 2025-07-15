#!/usr/bin/env python3
"""
Test-Skript für den Collections-Import

Dieses Skript demonstriert die Verwendung der neuen Collections-Import-Funktionalität.
"""

import django
import os
import sys

# Django Setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_manager.models import ShopifyStore
from shopify_manager.shopify_api import ShopifyAPIClient, ShopifyCollectionSync

def test_collections_import():
    """Test der Collections-Import-Funktionalität"""
    
    # Beispiel: Ersten Store aus der Datenbank holen
    try:
        store = ShopifyStore.objects.first()
        if not store:
            print("❌ Kein Store in der Datenbank gefunden")
            return
        
        print(f"📦 Teste Collections-Import für Store: {store.name}")
        
        # 1. API-Client testen
        print("\n1. 📡 Teste API-Verbindung...")
        client = ShopifyAPIClient(store)
        success, message = client.test_connection()
        if success:
            print(f"✅ API-Verbindung erfolgreich: {message}")
        else:
            print(f"❌ API-Verbindung fehlgeschlagen: {message}")
            return
        
        # 2. Collections abrufen (erste 10 zum Testen)
        print("\n2. 📂 Teste Collections-Abruf...")
        success, collections, message = client.fetch_collections(limit=10)
        if success:
            print(f"✅ Collections erfolgreich abgerufen: {message}")
            print(f"   Beispiel-Collections:")
            for i, collection in enumerate(collections[:3]):  # Zeige ersten 3
                print(f"   - {collection.get('id')}: {collection.get('title')}")
        else:
            print(f"❌ Collections-Abruf fehlgeschlagen: {message}")
            return
        
        # 3. Einzelne Collection mit Details abrufen
        if collections:
            first_collection_id = str(collections[0]['id'])
            print(f"\n3. 🔍 Teste einzelne Collection-Abruf (ID: {first_collection_id})...")
            success, collection, message = client.fetch_single_collection(first_collection_id)
            if success:
                print(f"✅ Collection erfolgreich abgerufen: {message}")
                print(f"   Details: {collection.get('title')} - {collection.get('description', 'Keine Beschreibung')[:50]}...")
            else:
                print(f"❌ Collection-Abruf fehlgeschlagen: {message}")
        
        # 4. Collections-Metafields abrufen
        if collections:
            first_collection_id = str(collections[0]['id'])
            print(f"\n4. 🏷️ Teste Collections-Metafields (ID: {first_collection_id})...")
            success, metafields, message = client.get_collection_metafields(first_collection_id)
            if success:
                print(f"✅ Collection-Metafields erfolgreich abgerufen: {message}")
                if metafields:
                    print(f"   Beispiel-Metafields:")
                    for mf in metafields[:3]:  # Zeige ersten 3
                        print(f"   - {mf.get('namespace')}.{mf.get('key')}: {str(mf.get('value', ''))[:50]}...")
                else:
                    print("   Keine Metafields gefunden")
            else:
                print(f"❌ Collection-Metafields-Abruf fehlgeschlagen: {message}")
        
        # 5. Collections-Sync testen
        print(f"\n5. 🔄 Teste Collections-Sync...")
        sync = ShopifyCollectionSync(store)
        log = sync.import_collections(limit=5, import_mode='new_only')
        
        if log.status == 'success':
            print(f"✅ Collections-Import erfolgreich:")
            print(f"   - Verarbeitet: {log.products_processed}")
            print(f"   - Erfolgreich: {log.products_success}")
            print(f"   - Fehlgeschlagen: {log.products_failed}")
        elif log.status == 'partial':
            print(f"⚠️ Collections-Import teilweise erfolgreich:")
            print(f"   - Verarbeitet: {log.products_processed}")
            print(f"   - Erfolgreich: {log.products_success}")
            print(f"   - Fehlgeschlagen: {log.products_failed}")
        else:
            print(f"❌ Collections-Import fehlgeschlagen: {log.error_message}")
        
        # 6. Lokale Collections anzeigen
        print(f"\n6. 📋 Lokale Collections im Store:")
        from shopify_manager.models import ShopifyCollection
        local_collections = ShopifyCollection.objects.filter(store=store)[:5]
        for collection in local_collections:
            print(f"   - {collection.shopify_id}: {collection.title}")
            print(f"     SEO: '{collection.seo_title}' / '{collection.seo_description[:50]}...'")
        
        print(f"\n✅ Test abgeschlossen!")
        
    except Exception as e:
        print(f"❌ Fehler beim Test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_collections_import()
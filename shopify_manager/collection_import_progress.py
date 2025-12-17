"""
Separate file für CollectionImportWithProgress da die shopify_api.py zu komplex ist
"""

from django.utils import timezone as django_timezone
from .models import ShopifySyncLog, ShopifyCollection, ShopifyStore
from .shopify_api import ShopifyAPIClient, ShopifyCollectionSync


class CollectionImportWithProgress:
    """Collection-Import mit Fortschrittsanzeige"""
    
    def __init__(self, store: ShopifyStore, import_id: str):
        self.store = store
        self.import_id = import_id
        self.api = ShopifyAPIClient(store)

    def _update_progress(self, current, total, message, success_count=0, failed_count=0):
        """Aktualisiert den Import-Fortschritt"""
        import time as time_module
        from .views import import_progress
        if self.import_id in import_progress:
            import_progress[self.import_id].update({
                'current': current,
                'total': total,
                'message': message,
                'success_count': success_count,
                'failed_count': failed_count,
                'last_update': time_module.time()
            })

    def import_collections_with_progress(self, import_mode: str = 'new_only', overwrite_existing: bool = False) -> ShopifySyncLog:
        """Importiert Collections mit Fortschrittsanzeige"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_collections',
            status='running'
        )
        
        try:
            self._update_progress(0, 0, 'Lösche alte Kategorien...' if import_mode == 'all' else 'Starte Import...')
            
            # Bei "Alle Collections" mit "Überschreiben" - alle lokalen Collections löschen
            if import_mode == 'all' and overwrite_existing:
                deleted_count = ShopifyCollectionSync(self.store)._delete_all_local_collections()
                print(f"🗑️ {deleted_count} lokale Collections gelöscht vor Neuimport")
                self._update_progress(0, 0, f'{deleted_count} alte Kategorien gelöscht, hole neue von Shopify...')
            
            # Collections von Shopify holen
            if import_mode == 'all':
                self._update_progress(0, 0, 'Hole alle Kategorien von Shopify...')
                success, collections, message = ShopifyCollectionSync(self.store)._fetch_all_collections()
            else:
                self._update_progress(0, 0, 'Hole neue Kategorien von Shopify...')
                success, collections, message = self.api.fetch_collections(limit=250)
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = django_timezone.now()
                log.save()
                self._update_progress(0, 0, f'Fehler: {message}')
                return log
            
            # Filter bei new_only Modus - nur neue Collections
            if import_mode == 'new_only':
                self._update_progress(0, len(collections), 'Prüfe bereits importierte Kategorien...')
                existing_ids = set(
                    ShopifyCollection.objects.filter(store=self.store)
                    .values_list('shopify_id', flat=True)
                )
                original_count = len(collections)
                collections = [c for c in collections if str(c.get('id')) not in existing_ids]
                print(f"Gefiltert: {len(collections)} neue Collections von ursprünglich {original_count}")
            
            total_collections = len(collections)
            if total_collections == 0:
                log.status = 'success'
                log.products_processed = 0
                log.products_success = 0
                log.completed_at = django_timezone.now()
                log.save()
                self._update_progress(0, 0, 'Keine neuen Kategorien gefunden - alle sind bereits importiert')
                return log
            
            log.products_processed = total_collections
            success_count = 0
            failed_count = 0
            
            self._update_progress(0, total_collections, f'Importiere {total_collections} Kategorien...')
            
            # Importiere Collections
            for i, collection_data in enumerate(collections, 1):
                try:
                    shopify_id = str(collection_data.get('id'))
                    
                    # Collection erstellen oder aktualisieren
                    collection, created = ShopifyCollectionSync(self.store)._create_or_update_collection(
                        collection_data, 
                        overwrite_existing=overwrite_existing
                    )
                    success_count += 1
                    
                    action = "erstellt" if created else "aktualisiert"
                    self._update_progress(
                        i, 
                        total_collections, 
                        f'Kategorie {i}/{total_collections}: {collection.title[:30]} {action}',
                        success_count=success_count,
                        failed_count=failed_count
                    )
                    
                    print(f"Collection {shopify_id} {action}: {collection.title}")
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Fehler beim Importieren von Collection {shopify_id}: {e}")
                    self._update_progress(
                        i, 
                        total_collections, 
                        f'Fehler bei Kategorie {i}/{total_collections}: {str(e)[:50]}',
                        success_count=success_count,
                        failed_count=failed_count
                    )
            
            # Log abschließen
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial_success'
            log.completed_at = django_timezone.now()
            log.save()
            
            final_message = f"Import abgeschlossen: {success_count} erfolgreich"
            if failed_count > 0:
                final_message += f", {failed_count} fehlgeschlagen"
            
            self._update_progress(
                total_collections, 
                total_collections, 
                final_message,
                success_count=success_count,
                failed_count=failed_count
            )
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = django_timezone.now()
            log.save()
            self._update_progress(0, 0, f'Fehler: {str(e)}')
            
        return log
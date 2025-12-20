"""
Shopify Backup Service

Erstellt umfassende Backups von Shopify-Daten:
- Produkte (inkl. Varianten, optional Bilder)
- Blogs & Blog-Posts
- Collections (Smart & Custom)
- Pages (statische Seiten)
- Menus (Navigation)
- Redirects (URL-Weiterleitungen)
- Metafields (Custom-Felder)
- Discount Codes
- Orders & Customers (optional)
"""

import requests
import json
import time
import io
import re
import zipfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction

from .models import ShopifyStore, ShopifyBackup, BackupItem


def sanitize_title(title: str) -> str:
    """Entfernt Emojis und andere problematische Unicode-Zeichen aus dem Titel"""
    if not title:
        return ""
    # Entferne alle Zeichen außerhalb des BMP (Basic Multilingual Plane)
    # Das sind die 4-Byte UTF-8 Zeichen wie Emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', title).strip()


class ShopifyBackupService:
    """Service für die Erstellung von Shopify-Backups"""

    def __init__(self, store: ShopifyStore, backup: ShopifyBackup):
        self.store = store
        self.backup = backup
        self.base_url = store.get_api_url()
        self.headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json'
        }
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 2 Requests pro Sekunde
        # Bei Resume: Vorhandene Größe aus DB laden
        self.total_size = backup.total_size_bytes or 0
        # Limit pro Durchlauf (100 Elemente, dann Pause)
        self.ITEMS_PER_SESSION = 100
        self.items_saved_this_session = 0
        self.session_limit_reached = False

    def _rate_limit(self):
        """Wartet die minimale Zeit zwischen API-Requests ab"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Macht einen Rate-Limited API Request mit Retry-Logik"""
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = requests.request(method, url, headers=self.headers, **kwargs)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue

                return response

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise

        return response

    def _fetch_all_paginated(self, endpoint: str, key: str, params: dict = None) -> List[Dict]:
        """Holt alle Daten von einem paginierten Endpoint"""
        all_items = []
        params = params or {}
        params['limit'] = 250

        url = f"{self.base_url}/{endpoint}"

        while url:
            response = self._make_request('GET', url, params=params if not all_items else None, timeout=30)

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get(key, [])
            all_items.extend(items)

            # Pagination über Link-Header
            link_header = response.headers.get('Link', '')
            url = None
            if 'rel="next"' in link_header:
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        url = link.split('<')[1].split('>')[0]
                        break

        return all_items

    def _item_exists(self, item_type: str, shopify_id: int) -> bool:
        """Prüft ob ein Item bereits im Backup existiert (für Resume-Funktion)"""
        return self.backup.items.filter(item_type=item_type, shopify_id=shopify_id).exists()

    def _check_session_limit(self) -> bool:
        """Prüft ob das Session-Limit erreicht wurde"""
        return self.items_saved_this_session >= self.ITEMS_PER_SESSION

    def _save_backup_item(self, item_type: str, shopify_id: int, title: str,
                          raw_data: dict, image_url: str = '', parent_id: int = None,
                          image_data: bytes = None):
        """Speichert ein Backup-Element in der Datenbank (überspringt wenn bereits vorhanden)"""
        # Prüfen ob Item bereits existiert (Resume-Fall)
        if self._item_exists(item_type, shopify_id):
            return None

        # Titel sanitizen (Emojis entfernen für MySQL-Kompatibilität)
        clean_title = sanitize_title(title) if title else ''
        item = BackupItem.objects.create(
            backup=self.backup,
            item_type=item_type,
            shopify_id=shopify_id,
            title=clean_title,
            raw_data=raw_data,
            image_url=image_url,
            parent_id=parent_id,
            image_data=image_data
        )
        # Größe tracken
        self.total_size += item.get_data_size()
        # Session-Zähler nur für Hauptelemente erhöhen (nicht für Bilder)
        # Bilder gehören zu ihren Eltern und zählen nicht als separate Elemente
        if item_type not in ('product_image', 'blog_image'):
            self.items_saved_this_session += 1
        return item

    def _download_image(self, url: str) -> Optional[bytes]:
        """Lädt ein Bild herunter und gibt die Bytes zurück"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
        except:
            pass
        return None

    def _update_progress(self, step: str, message: str, save_counts: bool = False):
        """Aktualisiert den Fortschritt in der Datenbank"""
        self.backup.current_step = step
        # Emojis aus der Nachricht entfernen (MySQL-Kompatibilität)
        self.backup.progress_message = sanitize_title(message) if message else ''

        if save_counts:
            # Auch alle Zähler speichern für Live-Updates
            self.backup.total_size_bytes = self.total_size
            self.backup.save(update_fields=[
                'current_step', 'progress_message',
                'products_count', 'blogs_count', 'posts_count',
                'collections_count', 'pages_count', 'menus_count',
                'redirects_count', 'metafields_count', 'discounts_count',
                'orders_count', 'customers_count', 'images_count',
                'total_size_bytes'
            ])
        else:
            self.backup.save(update_fields=['current_step', 'progress_message'])

    def _pause_backup(self, message: str) -> Tuple[bool, str]:
        """Pausiert das Backup nach Erreichen des Session-Limits"""
        self.backup.status = 'paused'
        self.backup.total_size_bytes = self.total_size
        saved_total = self.backup.items.count()
        self.backup.progress_message = f'{saved_total} Elemente gesichert. Klicken Sie "Weiter laden" für mehr.'
        self.backup.save()
        return True, f"Backup pausiert: {self.items_saved_this_session} Elemente in diesem Durchlauf gesichert. {message}"

    def create_backup(self) -> Tuple[bool, str]:
        """Hauptmethode - erstellt komplettes Backup (max. 100 Elemente pro Durchlauf)"""
        try:
            self.backup.status = 'running'
            self._update_progress('init', 'Backup wird gestartet...')

            # Produkte
            if self.backup.include_products and not self._check_session_limit():
                self._update_progress('products', 'Produkte werden gesichert...')
                self._backup_products()
                if self._check_session_limit():
                    return self._pause_backup('Produkte werden beim nächsten Durchlauf fortgesetzt.')

            # Blogs & Posts
            if self.backup.include_blogs and not self._check_session_limit():
                self._update_progress('blogs', 'Blogs werden gesichert...')
                self._backup_blogs()
                if self._check_session_limit():
                    return self._pause_backup('Blogs werden beim nächsten Durchlauf fortgesetzt.')

            # Collections
            if self.backup.include_collections and not self._check_session_limit():
                self._update_progress('collections', 'Collections werden gesichert...')
                self._backup_collections()
                if self._check_session_limit():
                    return self._pause_backup('Collections werden beim nächsten Durchlauf fortgesetzt.')

            # Pages
            if self.backup.include_pages and not self._check_session_limit():
                self._update_progress('pages', 'Seiten werden gesichert...')
                self._backup_pages()
                if self._check_session_limit():
                    return self._pause_backup('Seiten werden beim nächsten Durchlauf fortgesetzt.')

            # Menus
            if self.backup.include_menus and not self._check_session_limit():
                self._update_progress('menus', 'Menüs werden gesichert...')
                self._backup_menus()
                if self._check_session_limit():
                    return self._pause_backup('Menüs werden beim nächsten Durchlauf fortgesetzt.')

            # Redirects
            if self.backup.include_redirects and not self._check_session_limit():
                self._update_progress('redirects', 'Weiterleitungen werden gesichert...')
                self._backup_redirects()
                if self._check_session_limit():
                    return self._pause_backup('Weiterleitungen werden beim nächsten Durchlauf fortgesetzt.')

            # Metafields
            if self.backup.include_metafields and not self._check_session_limit():
                self._update_progress('metafields', 'Metafields werden gesichert...')
                self._backup_metafields()
                if self._check_session_limit():
                    return self._pause_backup('Metafields werden beim nächsten Durchlauf fortgesetzt.')

            # Discounts
            if self.backup.include_discounts and not self._check_session_limit():
                self._update_progress('discounts', 'Rabattcodes werden gesichert...')
                self._backup_discounts()
                if self._check_session_limit():
                    return self._pause_backup('Rabattcodes werden beim nächsten Durchlauf fortgesetzt.')

            # Orders
            if self.backup.include_orders and not self._check_session_limit():
                self._update_progress('orders', 'Bestellungen werden gesichert...')
                self._backup_orders()
                if self._check_session_limit():
                    return self._pause_backup('Bestellungen werden beim nächsten Durchlauf fortgesetzt.')

            # Customers
            if self.backup.include_customers and not self._check_session_limit():
                self._update_progress('customers', 'Kundendaten werden gesichert...')
                self._backup_customers()
                if self._check_session_limit():
                    return self._pause_backup('Kundendaten werden beim nächsten Durchlauf fortgesetzt.')

            # Backup abschließen - nur wenn alle Kategorien fertig
            self._update_progress('finalizing', 'Backup wird abgeschlossen...')
            self.backup.status = 'completed'
            self.backup.completed_at = timezone.now()
            self.backup.total_size_bytes = self.total_size
            self.backup.current_step = ''
            self.backup.progress_message = ''
            self.backup.save()

            return True, "Backup erfolgreich erstellt"

        except Exception as e:
            error_str = str(e).lower()
            # Bei DB-Verbindungsfehlern: Pausieren statt Fehlschlagen (wiederholbar)
            is_recoverable = any(err in error_str for err in [
                'lost connection', 'mysql', 'connection', 'timeout',
                'operational', 'database', 'server has gone away'
            ])

            if is_recoverable:
                # Versuche den Status auf paused zu setzen
                try:
                    self.backup.status = 'paused'
                    self.backup.progress_message = f'Automatisch pausiert: Verbindungsfehler. Klicken Sie auf Weiter laden.'
                    self.backup.save()
                    return False, f"Backup pausiert wegen Verbindungsfehler: {str(e)[:100]}"
                except:
                    # Wenn auch das fehlschlägt, direkt in DB schreiben
                    from django.db import connection
                    try:
                        connection.close()
                        connection.ensure_connection()
                        ShopifyBackup.objects.filter(id=self.backup.id).update(
                            status='paused',
                            progress_message='Automatisch pausiert: Verbindungsfehler. Klicken Sie auf Weiter laden.'
                        )
                    except:
                        pass
                    return False, f"Backup pausiert wegen Verbindungsfehler"
            else:
                # Echter Fehler
                self.backup.status = 'failed'
                self.backup.error_message = str(e)
                self.backup.current_step = 'error'
                self.backup.progress_message = f'Fehler: {str(e)[:200]}'
                self.backup.save()
                return False, f"Backup fehlgeschlagen: {str(e)}"

    def _backup_products(self):
        """Sichert alle Produkte (inkl. Bilder)"""
        self._update_progress('products', 'Produkte werden abgerufen...')
        products = self._fetch_all_paginated('products.json', 'products')
        total = len(products)

        # Zähle bereits gespeicherte Produkte (für Resume)
        saved_count = self.backup.items.filter(item_type='product').count()
        skipped = 0

        for idx, product in enumerate(products):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('product', product['id']):
                skipped += 1
                # Fortschritt anzeigen aber nicht speichern
                if idx % 20 == 0:
                    self._update_progress(
                        'products',
                        f'Überspringe {skipped} bereits gesicherte Produkte...',
                        save_counts=False
                    )
                continue

            # Neues Produkt - Zähler erhöhen
            saved_count += 1
            self.backup.products_count = saved_count

            # Alle 5 neue Produkte oder beim letzten: Live-Update speichern
            save_now = (saved_count % 5 == 0) or (idx == total - 1)
            self._update_progress(
                'products',
                f'Produkt {saved_count}/{total}: {product.get("title", "")[:40]}...',
                save_counts=save_now
            )

            # Erstes Bild als Hauptbild für das Produkt
            image_url = ''
            main_image_data = None
            if product.get('images'):
                image_url = product['images'][0].get('src', '')
                if image_url:
                    main_image_data = self._download_image(image_url)

            # Produkt sichern (mit Hauptbild)
            self._save_backup_item(
                item_type='product',
                shopify_id=product['id'],
                title=product.get('title', 'Unbekannt'),
                raw_data=product,
                image_url=image_url,
                image_data=main_image_data
            )

            # Alle Produktbilder sichern (inkl. Download)
            if product.get('images'):
                for img in product['images']:
                    # Session-Limit auch für Bilder prüfen
                    if self._check_session_limit():
                        break
                    img_url = img.get('src', '')
                    if img_url:
                        # Prüfen ob Bild bereits existiert
                        if self._item_exists('product_image', img['id']):
                            continue
                        image_data = self._download_image(img_url)
                        self._save_backup_item(
                            item_type='product_image',
                            shopify_id=img['id'],
                            title=f"Bild für {product.get('title', '')}",
                            raw_data=img,
                            image_url=img_url,
                            parent_id=product['id'],
                            image_data=image_data
                        )
                        if image_data:
                            self.backup.images_count += 1

        # Final save mit korrektem Zähler
        self.backup.products_count = saved_count
        self._update_progress('products', f'{saved_count} Produkte gesichert', save_counts=True)

    def _backup_blogs(self):
        """Sichert Blogs und Blog-Posts (inkl. Bilder)"""
        self._update_progress('blogs', 'Blogs werden abgerufen...')
        blogs = self._fetch_all_paginated('blogs.json', 'blogs')
        total_blogs = len(blogs)

        # Zähle bereits gespeicherte (für Resume)
        saved_blogs = self.backup.items.filter(item_type='blog').count()
        saved_posts = self.backup.items.filter(item_type='blog_post').count()

        for blog_idx, blog in enumerate(blogs):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob Blog bereits gespeichert
            if not self._item_exists('blog', blog['id']):
                saved_blogs += 1
                self._save_backup_item(
                    item_type='blog',
                    shopify_id=blog['id'],
                    title=blog.get('title', 'Unbekannt'),
                    raw_data=blog
                )

            self.backup.blogs_count = saved_blogs
            self._update_progress(
                'blogs',
                f'Blog {saved_blogs}/{total_blogs}: {blog.get("title", "")[:40]}...',
                save_counts=True
            )

            # Blog-Posts für diesen Blog holen
            self._update_progress('blogs', f'Lade Beiträge von "{blog.get("title", "")[:30]}"...')
            articles = self._fetch_all_paginated(
                f'blogs/{blog["id"]}/articles.json',
                'articles'
            )
            total_articles = len(articles)

            for idx, article in enumerate(articles):
                # Session-Limit prüfen
                if self._check_session_limit():
                    break

                # Prüfen ob Post bereits gespeichert (Resume-Fall)
                if self._item_exists('blog_post', article['id']):
                    continue

                saved_posts += 1
                self.backup.posts_count = saved_posts

                # Alle 5 Posts oder beim letzten: Live-Update speichern
                save_now = (saved_posts % 5 == 0) or (idx == total_articles - 1)
                self._update_progress(
                    'blogs',
                    f'Beitrag {saved_posts}: {article.get("title", "")[:35]}...',
                    save_counts=save_now
                )

                image_url = article.get('image', {}).get('src', '') if article.get('image') else ''

                # Bild automatisch herunterladen wenn vorhanden
                image_data = None
                if image_url:
                    image_data = self._download_image(image_url)
                    if image_data:
                        self.backup.images_count += 1

                self._save_backup_item(
                    item_type='blog_post',
                    shopify_id=article['id'],
                    title=article.get('title', 'Unbekannt'),
                    raw_data=article,
                    image_url=image_url,
                    parent_id=blog['id'],
                    image_data=image_data
                )

        # Final save
        self.backup.blogs_count = saved_blogs
        self.backup.posts_count = saved_posts
        self._update_progress('blogs', f'{saved_blogs} Blogs, {saved_posts} Beiträge gesichert', save_counts=True)

    def _backup_collections(self):
        """Sichert Custom und Smart Collections (inkl. Bilder)"""
        # Zähle bereits gespeicherte (für Resume)
        saved_count = self.backup.items.filter(item_type='collection').count()

        # Custom Collections
        self._update_progress('collections', 'Custom Collections werden abgerufen...')
        custom_collections = self._fetch_all_paginated('custom_collections.json', 'custom_collections')
        total_custom = len(custom_collections)

        for idx, collection in enumerate(custom_collections):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('collection', collection['id']):
                continue

            collection['collection_type'] = 'custom'
            image_url = collection.get('image', {}).get('src', '') if collection.get('image') else ''

            saved_count += 1
            self.backup.collections_count = saved_count
            save_now = (saved_count % 5 == 0) or (idx == total_custom - 1)
            self._update_progress(
                'collections',
                f'Custom Collection {saved_count}: {collection.get("title", "")[:35]}...',
                save_counts=save_now
            )

            # Bild automatisch herunterladen wenn vorhanden
            image_data = None
            if image_url:
                image_data = self._download_image(image_url)
                if image_data:
                    self.backup.images_count += 1

            self._save_backup_item(
                item_type='collection',
                shopify_id=collection['id'],
                title=collection.get('title', 'Unbekannt'),
                raw_data=collection,
                image_url=image_url,
                image_data=image_data
            )

        # Smart Collections (nur wenn Limit noch nicht erreicht)
        if not self._check_session_limit():
            self._update_progress('collections', 'Smart Collections werden abgerufen...', save_counts=True)
            smart_collections = self._fetch_all_paginated('smart_collections.json', 'smart_collections')
            total_smart = len(smart_collections)

            for idx, collection in enumerate(smart_collections):
                # Session-Limit prüfen
                if self._check_session_limit():
                    break

                # Prüfen ob bereits gespeichert (Resume-Fall)
                if self._item_exists('collection', collection['id']):
                    continue

                collection['collection_type'] = 'smart'
                image_url = collection.get('image', {}).get('src', '') if collection.get('image') else ''

                saved_count += 1
                self.backup.collections_count = saved_count
                save_now = (saved_count % 5 == 0) or (idx == total_smart - 1)
                self._update_progress(
                    'collections',
                    f'Smart Collection {saved_count}: {collection.get("title", "")[:35]}...',
                    save_counts=save_now
                )

                # Bild automatisch herunterladen wenn vorhanden
                image_data = None
                if image_url:
                    image_data = self._download_image(image_url)
                    if image_data:
                        self.backup.images_count += 1

                self._save_backup_item(
                    item_type='collection',
                    shopify_id=collection['id'],
                    title=collection.get('title', 'Unbekannt'),
                    raw_data=collection,
                    image_url=image_url,
                    image_data=image_data
                )

        # Final save
        self.backup.collections_count = saved_count
        self._update_progress('collections', f'{saved_count} Collections gesichert', save_counts=True)

    def _backup_pages(self):
        """Sichert statische Seiten"""
        self._update_progress('pages', 'Seiten werden abgerufen...')
        pages = self._fetch_all_paginated('pages.json', 'pages')
        total = len(pages)

        # Zähle bereits gespeicherte (für Resume)
        saved_count = self.backup.items.filter(item_type='page').count()

        for idx, page in enumerate(pages):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('page', page['id']):
                continue

            saved_count += 1
            self.backup.pages_count = saved_count

            # Alle 5 Seiten oder beim letzten: Live-Update speichern
            save_now = (saved_count % 5 == 0) or (idx == total - 1)
            self._update_progress(
                'pages',
                f'Seite {saved_count}/{total}: {page.get("title", "")[:40]}...',
                save_counts=save_now
            )

            self._save_backup_item(
                item_type='page',
                shopify_id=page['id'],
                title=page.get('title', 'Unbekannt'),
                raw_data=page
            )

        # Final save
        self.backup.pages_count = saved_count
        self._update_progress('pages', f'{saved_count} Seiten gesichert', save_counts=True)

    def _backup_menus(self):
        """Sichert Navigationsmenüs"""
        # Shopify nutzt "menus" nicht direkt, sondern "navigation"
        # Wir holen über den GraphQL oder REST API die Menüs
        try:
            self._update_progress('menus', 'Menüs werden abgerufen...')
            response = self._make_request(
                'GET',
                f"{self.base_url}/menus.json",
                timeout=30
            )

            if response.status_code == 200:
                menus = response.json().get('menus', [])
                total = len(menus)

                # Zähle bereits gespeicherte (für Resume)
                saved_count = self.backup.items.filter(item_type='menu').count()

                for idx, menu in enumerate(menus):
                    # Session-Limit prüfen
                    if self._check_session_limit():
                        break

                    # Prüfen ob bereits gespeichert (Resume-Fall)
                    if self._item_exists('menu', menu['id']):
                        continue

                    saved_count += 1
                    self.backup.menus_count = saved_count

                    # Alle 5 Menüs oder beim letzten: Live-Update speichern
                    save_now = (saved_count % 5 == 0) or (idx == total - 1)
                    self._update_progress(
                        'menus',
                        f'Menü {saved_count}/{total}: {menu.get("title", "")[:40]}...',
                        save_counts=save_now
                    )

                    self._save_backup_item(
                        item_type='menu',
                        shopify_id=menu['id'],
                        title=menu.get('title', 'Unbekannt'),
                        raw_data=menu
                    )

                # Final save
                self.backup.menus_count = saved_count
                self._update_progress('menus', f'{saved_count} Menüs gesichert', save_counts=True)
        except:
            # Menüs sind optional, Fehler ignorieren
            pass

    def _backup_redirects(self):
        """Sichert URL-Weiterleitungen"""
        self._update_progress('redirects', 'Weiterleitungen werden abgerufen...')
        redirects = self._fetch_all_paginated('redirects.json', 'redirects')
        total = len(redirects)

        # Zähle bereits gespeicherte (für Resume)
        saved_count = self.backup.items.filter(item_type='redirect').count()

        for idx, redirect in enumerate(redirects):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('redirect', redirect['id']):
                continue

            saved_count += 1
            self.backup.redirects_count = saved_count

            # Alle 5 Redirects oder beim letzten: Live-Update speichern
            save_now = (saved_count % 5 == 0) or (idx == total - 1)
            self._update_progress(
                'redirects',
                f'Weiterleitung {saved_count}/{total}: {redirect.get("path", "")[:30]}...',
                save_counts=save_now
            )

            self._save_backup_item(
                item_type='redirect',
                shopify_id=redirect['id'],
                title=f"{redirect.get('path', '')} -> {redirect.get('target', '')}",
                raw_data=redirect
            )

        # Final save
        self.backup.redirects_count = saved_count
        self._update_progress('redirects', f'{saved_count} Weiterleitungen gesichert', save_counts=True)

    def _backup_metafields(self):
        """Sichert Shop-Metafields"""
        try:
            self._update_progress('metafields', 'Metafields werden abgerufen...')
            response = self._make_request(
                'GET',
                f"{self.base_url}/metafields.json",
                params={'limit': 250},
                timeout=30
            )

            if response.status_code == 200:
                metafields = response.json().get('metafields', [])
                total = len(metafields)

                # Zähle bereits gespeicherte (für Resume)
                saved_count = self.backup.items.filter(item_type='metafield').count()

                for idx, mf in enumerate(metafields):
                    # Session-Limit prüfen
                    if self._check_session_limit():
                        break

                    # Prüfen ob bereits gespeichert (Resume-Fall)
                    if self._item_exists('metafield', mf['id']):
                        continue

                    saved_count += 1
                    self.backup.metafields_count = saved_count

                    # Alle 5 Metafields oder beim letzten: Live-Update speichern
                    save_now = (saved_count % 5 == 0) or (idx == total - 1)
                    self._update_progress(
                        'metafields',
                        f'Metafield {saved_count}/{total}: {mf.get("namespace", "")}.{mf.get("key", "")[:20]}...',
                        save_counts=save_now
                    )

                    self._save_backup_item(
                        item_type='metafield',
                        shopify_id=mf['id'],
                        title=f"{mf.get('namespace', '')}.{mf.get('key', '')}",
                        raw_data=mf
                    )

                # Final save
                self.backup.metafields_count = saved_count
                self._update_progress('metafields', f'{saved_count} Metafields gesichert', save_counts=True)
        except:
            pass

    def _backup_discounts(self):
        """Sichert Rabattcodes"""
        # Price Rules und Discount Codes
        try:
            self._update_progress('discounts', 'Rabattcodes werden abgerufen...')
            price_rules = self._fetch_all_paginated('price_rules.json', 'price_rules')
            total_rules = len(price_rules)

            # Zähle bereits gespeicherte (für Resume)
            saved_count = self.backup.items.filter(item_type='discount').count()

            for rule_idx, rule in enumerate(price_rules):
                # Session-Limit prüfen
                if self._check_session_limit():
                    break

                self._update_progress(
                    'discounts',
                    f'Price Rule {rule_idx + 1}/{total_rules}: {rule.get("title", "")[:30]}...',
                    save_counts=True
                )

                # Discount Codes für diese Price Rule holen
                discount_codes = self._fetch_all_paginated(
                    f'price_rules/{rule["id"]}/discount_codes.json',
                    'discount_codes'
                )
                total_codes = len(discount_codes)

                for idx, code in enumerate(discount_codes):
                    # Session-Limit prüfen
                    if self._check_session_limit():
                        break

                    # Prüfen ob bereits gespeichert (Resume-Fall)
                    if self._item_exists('discount', code['id']):
                        continue

                    saved_count += 1
                    self.backup.discounts_count = saved_count

                    # Alle 5 Codes oder beim letzten: Live-Update speichern
                    save_now = (saved_count % 5 == 0) or (idx == total_codes - 1)
                    self._update_progress(
                        'discounts',
                        f'Rabattcode {saved_count}: {code.get("code", "")[:20]}...',
                        save_counts=save_now
                    )

                    code['price_rule'] = rule  # Rule-Daten hinzufügen
                    self._save_backup_item(
                        item_type='discount',
                        shopify_id=code['id'],
                        title=code.get('code', 'Unbekannt'),
                        raw_data=code,
                        parent_id=rule['id']
                    )

            # Final save
            self.backup.discounts_count = saved_count
            self._update_progress('discounts', f'{saved_count} Rabattcodes gesichert', save_counts=True)
        except:
            pass

    def _backup_orders(self):
        """Sichert Bestellungen"""
        self._update_progress('orders', 'Bestellungen werden abgerufen...')
        orders = self._fetch_all_paginated('orders.json', 'orders', {'status': 'any'})
        total = len(orders)

        # Zähle bereits gespeicherte (für Resume)
        saved_count = self.backup.items.filter(item_type='order').count()

        for idx, order in enumerate(orders):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('order', order['id']):
                continue

            saved_count += 1
            self.backup.orders_count = saved_count

            # Alle 5 Bestellungen oder beim letzten: Live-Update speichern
            save_now = (saved_count % 5 == 0) or (idx == total - 1)
            self._update_progress(
                'orders',
                f'Bestellung {saved_count}/{total}: #{order.get("order_number", order["id"])}...',
                save_counts=save_now
            )

            self._save_backup_item(
                item_type='order',
                shopify_id=order['id'],
                title=f"Bestellung #{order.get('order_number', order['id'])}",
                raw_data=order
            )

        # Final save
        self.backup.orders_count = saved_count
        self._update_progress('orders', f'{saved_count} Bestellungen gesichert', save_counts=True)

    def _backup_customers(self):
        """Sichert Kundendaten"""
        self._update_progress('customers', 'Kundendaten werden abgerufen...')
        customers = self._fetch_all_paginated('customers.json', 'customers')
        total = len(customers)

        # Zähle bereits gespeicherte (für Resume)
        saved_count = self.backup.items.filter(item_type='customer').count()

        for idx, customer in enumerate(customers):
            # Session-Limit prüfen
            if self._check_session_limit():
                break

            # Prüfen ob bereits gespeichert (Resume-Fall)
            if self._item_exists('customer', customer['id']):
                continue

            saved_count += 1
            self.backup.customers_count = saved_count

            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            if not name:
                name = customer.get('email', 'Unbekannt')

            # Alle 5 Kunden oder beim letzten: Live-Update speichern
            save_now = (saved_count % 5 == 0) or (idx == total - 1)
            self._update_progress(
                'customers',
                f'Kunde {saved_count}/{total}: {name[:30]}...',
                save_counts=save_now
            )

            self._save_backup_item(
                item_type='customer',
                shopify_id=customer['id'],
                title=name,
                raw_data=customer
            )

        # Final save
        self.backup.customers_count = saved_count
        self._update_progress('customers', f'{saved_count} Kundendaten gesichert', save_counts=True)

    def generate_download_zip(self) -> io.BytesIO:
        """Generiert eine ZIP-Datei mit allen Backup-Daten"""
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Manifest erstellen
            manifest = {
                'backup_name': self.backup.name,
                'store': self.store.name,
                'shop_domain': self.store.shop_domain,
                'created_at': self.backup.created_at.isoformat(),
                'statistics': {
                    'products': self.backup.products_count,
                    'blogs': self.backup.blogs_count,
                    'posts': self.backup.posts_count,
                    'collections': self.backup.collections_count,
                    'pages': self.backup.pages_count,
                    'menus': self.backup.menus_count,
                    'redirects': self.backup.redirects_count,
                    'metafields': self.backup.metafields_count,
                    'discounts': self.backup.discounts_count,
                    'orders': self.backup.orders_count,
                    'customers': self.backup.customers_count,
                    'images': self.backup.images_count,
                }
            }
            zip_file.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))

            # Daten nach Typ gruppieren und exportieren
            item_types = [
                ('product', 'products.json'),
                ('blog', 'blogs.json'),
                ('blog_post', 'posts.json'),
                ('collection', 'collections.json'),
                ('page', 'pages.json'),
                ('menu', 'menus.json'),
                ('redirect', 'redirects.json'),
                ('metafield', 'metafields.json'),
                ('discount', 'discounts.json'),
                ('order', 'orders.json'),
                ('customer', 'customers.json'),
            ]

            for item_type, filename in item_types:
                items = self.backup.items.filter(item_type=item_type)
                if items.exists():
                    data = [item.raw_data for item in items]
                    zip_file.writestr(filename, json.dumps(data, indent=2, ensure_ascii=False))

            # Bilder in separatem Ordner
            image_types = ['product_image', 'blog_image']
            for img_type in image_types:
                images = self.backup.items.filter(item_type=img_type, image_data__isnull=False)
                for img in images:
                    if img.image_data:
                        folder = 'images/products' if img_type == 'product_image' else 'images/posts'
                        # Dateinamen aus URL extrahieren
                        filename = img.image_url.split('/')[-1].split('?')[0] if img.image_url else f'{img.shopify_id}.jpg'
                        zip_file.writestr(f'{folder}/{filename}', img.image_data)

        zip_buffer.seek(0)
        return zip_buffer

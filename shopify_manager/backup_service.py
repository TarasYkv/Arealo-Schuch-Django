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
        self.total_size = 0

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

    def _save_backup_item(self, item_type: str, shopify_id: int, title: str,
                          raw_data: dict, image_url: str = '', parent_id: int = None,
                          image_data: bytes = None):
        """Speichert ein Backup-Element in der Datenbank"""
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

    def _update_progress(self, step: str, message: str):
        """Aktualisiert den Fortschritt in der Datenbank"""
        self.backup.current_step = step
        self.backup.progress_message = message
        self.backup.save(update_fields=['current_step', 'progress_message'])

    def create_backup(self) -> Tuple[bool, str]:
        """Hauptmethode - erstellt komplettes Backup"""
        try:
            self.backup.status = 'running'
            self._update_progress('init', 'Backup wird gestartet...')

            # Produkte
            if self.backup.include_products:
                self._update_progress('products', 'Produkte werden gesichert...')
                self._backup_products()

            # Blogs & Posts
            if self.backup.include_blogs:
                self._update_progress('blogs', 'Blogs werden gesichert...')
                self._backup_blogs()

            # Collections
            if self.backup.include_collections:
                self._update_progress('collections', 'Collections werden gesichert...')
                self._backup_collections()

            # Pages
            if self.backup.include_pages:
                self._update_progress('pages', 'Seiten werden gesichert...')
                self._backup_pages()

            # Menus
            if self.backup.include_menus:
                self._update_progress('menus', 'Menüs werden gesichert...')
                self._backup_menus()

            # Redirects
            if self.backup.include_redirects:
                self._update_progress('redirects', 'Weiterleitungen werden gesichert...')
                self._backup_redirects()

            # Metafields
            if self.backup.include_metafields:
                self._update_progress('metafields', 'Metafields werden gesichert...')
                self._backup_metafields()

            # Discounts
            if self.backup.include_discounts:
                self._update_progress('discounts', 'Rabattcodes werden gesichert...')
                self._backup_discounts()

            # Orders
            if self.backup.include_orders:
                self._update_progress('orders', 'Bestellungen werden gesichert...')
                self._backup_orders()

            # Customers
            if self.backup.include_customers:
                self._update_progress('customers', 'Kundendaten werden gesichert...')
                self._backup_customers()

            # Backup abschließen
            self._update_progress('finalizing', 'Backup wird abgeschlossen...')
            self.backup.status = 'completed'
            self.backup.completed_at = timezone.now()
            self.backup.total_size_bytes = self.total_size
            self.backup.current_step = ''
            self.backup.progress_message = ''
            self.backup.save()

            return True, "Backup erfolgreich erstellt"

        except Exception as e:
            self.backup.status = 'failed'
            self.backup.error_message = str(e)
            self.backup.current_step = 'error'
            self.backup.progress_message = f'Fehler: {str(e)[:200]}'
            self.backup.save()
            return False, f"Backup fehlgeschlagen: {str(e)}"

    def _backup_products(self):
        """Sichert alle Produkte"""
        self._update_progress('products', 'Produkte werden abgerufen...')
        products = self._fetch_all_paginated('products.json', 'products')
        total = len(products)
        count = 0
        images_count = 0

        for product in products:
            count += 1
            self._update_progress('products', f'Produkt {count} von {total}: {product.get("title", "")[:40]}...')

            # Produkt sichern
            image_url = ''
            if product.get('images'):
                image_url = product['images'][0].get('src', '')

            self._save_backup_item(
                item_type='product',
                shopify_id=product['id'],
                title=product.get('title', 'Unbekannt'),
                raw_data=product,
                image_url=image_url
            )

            # Optional: Produktbilder herunterladen
            if self.backup.include_product_images and product.get('images'):
                for img in product['images']:
                    img_url = img.get('src', '')
                    if img_url:
                        image_data = self._download_image(img_url) if self.backup.include_product_images else None
                        self._save_backup_item(
                            item_type='product_image',
                            shopify_id=img['id'],
                            title=f"Bild für {product.get('title', '')}",
                            raw_data=img,
                            image_url=img_url,
                            parent_id=product['id'],
                            image_data=image_data
                        )
                        images_count += 1

        self.backup.products_count = count
        self.backup.images_count += images_count
        self.backup.save()

    def _backup_blogs(self):
        """Sichert Blogs und Blog-Posts"""
        self._update_progress('blogs', 'Blogs werden abgerufen...')
        blogs = self._fetch_all_paginated('blogs.json', 'blogs')
        blogs_count = 0
        posts_count = 0

        for blog in blogs:
            blogs_count += 1
            self._update_progress('blogs', f'Blog: {blog.get("title", "")[:40]}...')

            # Blog sichern
            self._save_backup_item(
                item_type='blog',
                shopify_id=blog['id'],
                title=blog.get('title', 'Unbekannt'),
                raw_data=blog
            )

            # Blog-Posts für diesen Blog holen
            self._update_progress('blogs', f'Lade Beiträge von "{blog.get("title", "")[:30]}"...')
            articles = self._fetch_all_paginated(
                f'blogs/{blog["id"]}/articles.json',
                'articles'
            )

            for idx, article in enumerate(articles, 1):
                self._update_progress('blogs', f'Beitrag {idx}/{len(articles)}: {article.get("title", "")[:35]}...')
                image_url = article.get('image', {}).get('src', '') if article.get('image') else ''

                self._save_backup_item(
                    item_type='blog_post',
                    shopify_id=article['id'],
                    title=article.get('title', 'Unbekannt'),
                    raw_data=article,
                    image_url=image_url,
                    parent_id=blog['id']
                )
                posts_count += 1

                # Optional: Blog-Bilder herunterladen
                if self.backup.include_blog_images and image_url:
                    image_data = self._download_image(image_url)
                    if image_data:
                        self._save_backup_item(
                            item_type='blog_image',
                            shopify_id=article['id'],
                            title=f"Bild für {article.get('title', '')}",
                            raw_data={'image_url': image_url},
                            image_url=image_url,
                            parent_id=article['id'],
                            image_data=image_data
                        )
                        self.backup.images_count += 1

        self.backup.blogs_count = blogs_count
        self.backup.posts_count = posts_count
        self.backup.save()

    def _backup_collections(self):
        """Sichert Custom und Smart Collections"""
        count = 0

        # Custom Collections
        custom_collections = self._fetch_all_paginated('custom_collections.json', 'custom_collections')
        for collection in custom_collections:
            collection['collection_type'] = 'custom'
            image_url = collection.get('image', {}).get('src', '') if collection.get('image') else ''

            self._save_backup_item(
                item_type='collection',
                shopify_id=collection['id'],
                title=collection.get('title', 'Unbekannt'),
                raw_data=collection,
                image_url=image_url
            )
            count += 1

        # Smart Collections
        smart_collections = self._fetch_all_paginated('smart_collections.json', 'smart_collections')
        for collection in smart_collections:
            collection['collection_type'] = 'smart'
            image_url = collection.get('image', {}).get('src', '') if collection.get('image') else ''

            self._save_backup_item(
                item_type='collection',
                shopify_id=collection['id'],
                title=collection.get('title', 'Unbekannt'),
                raw_data=collection,
                image_url=image_url
            )
            count += 1

        self.backup.collections_count = count
        self.backup.save()

    def _backup_pages(self):
        """Sichert statische Seiten"""
        pages = self._fetch_all_paginated('pages.json', 'pages')
        count = 0

        for page in pages:
            self._save_backup_item(
                item_type='page',
                shopify_id=page['id'],
                title=page.get('title', 'Unbekannt'),
                raw_data=page
            )
            count += 1

        self.backup.pages_count = count
        self.backup.save()

    def _backup_menus(self):
        """Sichert Navigationsmenüs"""
        # Shopify nutzt "menus" nicht direkt, sondern "navigation"
        # Wir holen über den GraphQL oder REST API die Menüs
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/menus.json",
                timeout=30
            )

            if response.status_code == 200:
                menus = response.json().get('menus', [])
                count = 0

                for menu in menus:
                    self._save_backup_item(
                        item_type='menu',
                        shopify_id=menu['id'],
                        title=menu.get('title', 'Unbekannt'),
                        raw_data=menu
                    )
                    count += 1

                self.backup.menus_count = count
                self.backup.save()
        except:
            # Menüs sind optional, Fehler ignorieren
            pass

    def _backup_redirects(self):
        """Sichert URL-Weiterleitungen"""
        redirects = self._fetch_all_paginated('redirects.json', 'redirects')
        count = 0

        for redirect in redirects:
            self._save_backup_item(
                item_type='redirect',
                shopify_id=redirect['id'],
                title=f"{redirect.get('path', '')} -> {redirect.get('target', '')}",
                raw_data=redirect
            )
            count += 1

        self.backup.redirects_count = count
        self.backup.save()

    def _backup_metafields(self):
        """Sichert Shop-Metafields"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/metafields.json",
                params={'limit': 250},
                timeout=30
            )

            if response.status_code == 200:
                metafields = response.json().get('metafields', [])
                count = 0

                for mf in metafields:
                    self._save_backup_item(
                        item_type='metafield',
                        shopify_id=mf['id'],
                        title=f"{mf.get('namespace', '')}.{mf.get('key', '')}",
                        raw_data=mf
                    )
                    count += 1

                self.backup.metafields_count = count
                self.backup.save()
        except:
            pass

    def _backup_discounts(self):
        """Sichert Rabattcodes"""
        # Price Rules und Discount Codes
        try:
            price_rules = self._fetch_all_paginated('price_rules.json', 'price_rules')
            count = 0

            for rule in price_rules:
                # Discount Codes für diese Price Rule holen
                discount_codes = self._fetch_all_paginated(
                    f'price_rules/{rule["id"]}/discount_codes.json',
                    'discount_codes'
                )

                for code in discount_codes:
                    code['price_rule'] = rule  # Rule-Daten hinzufügen
                    self._save_backup_item(
                        item_type='discount',
                        shopify_id=code['id'],
                        title=code.get('code', 'Unbekannt'),
                        raw_data=code,
                        parent_id=rule['id']
                    )
                    count += 1

            self.backup.discounts_count = count
            self.backup.save()
        except:
            pass

    def _backup_orders(self):
        """Sichert Bestellungen"""
        orders = self._fetch_all_paginated('orders.json', 'orders', {'status': 'any'})
        count = 0

        for order in orders:
            self._save_backup_item(
                item_type='order',
                shopify_id=order['id'],
                title=f"Bestellung #{order.get('order_number', order['id'])}",
                raw_data=order
            )
            count += 1

        self.backup.orders_count = count
        self.backup.save()

    def _backup_customers(self):
        """Sichert Kundendaten"""
        customers = self._fetch_all_paginated('customers.json', 'customers')
        count = 0

        for customer in customers:
            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            if not name:
                name = customer.get('email', 'Unbekannt')

            self._save_backup_item(
                item_type='customer',
                shopify_id=customer['id'],
                title=name,
                raw_data=customer
            )
            count += 1

        self.backup.customers_count = count
        self.backup.save()

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

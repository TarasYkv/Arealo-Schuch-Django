"""
Shopify Backup Compare Service

Vergleicht ein Backup mit dem aktuellen Stand auf Shopify:
- Gelöschte Elemente (im Backup, aber nicht mehr auf Shopify)
- Neue Elemente (auf Shopify, aber nicht im Backup)
- Geänderte Elemente (unterschiedliche Daten)
"""

import requests
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from django.utils import timezone

from .models import ShopifyStore, ShopifyBackup, BackupItem


@dataclass
class CompareResult:
    """Ergebnis eines Vergleichs für ein Element"""
    item_type: str
    shopify_id: int
    title: str
    status: str  # 'deleted', 'new', 'changed', 'unchanged'
    changes: List[str] = None  # Liste der Änderungen
    backup_data: Dict = None
    current_data: Dict = None
    backup_item_id: int = None  # ID des BackupItem für Aktionen

    def __post_init__(self):
        if self.changes is None:
            self.changes = []


class ShopifyCompareService:
    """Service für den Vergleich von Backups mit Shopify"""

    def __init__(self, store: ShopifyStore, backup: ShopifyBackup):
        self.store = store
        self.backup = backup
        self.base_url = store.get_api_url()
        self.headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json'
        }
        self.last_request_time = 0
        self.min_request_interval = 0.5

    def _rate_limit(self):
        """Wartet die minimale Zeit zwischen API-Requests ab"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Macht einen Rate-Limited API Request"""
        self._rate_limit()
        return requests.request(method, url, headers=self.headers, **kwargs)

    def _fetch_all_paginated(self, endpoint: str, key: str) -> List[Dict]:
        """Holt alle Daten von einem paginierten Endpoint"""
        all_items = []
        url = f"{self.base_url}/{endpoint}"
        params = {'limit': 250}

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

    def compare_all(self) -> Dict[str, List[CompareResult]]:
        """Vergleicht alle Backup-Kategorien mit Shopify"""
        results = {}

        # Nur die Kategorien vergleichen, die im Backup enthalten sind
        if self.backup.include_products:
            results['products'] = self._compare_products()

        if self.backup.include_blogs:
            results['blogs'] = self._compare_blogs()
            results['blog_posts'] = self._compare_blog_posts()

        if self.backup.include_collections:
            results['collections'] = self._compare_collections()

        if self.backup.include_pages:
            results['pages'] = self._compare_pages()

        if self.backup.include_redirects:
            results['redirects'] = self._compare_redirects()

        return results

    def compare_category(self, category: str) -> List[CompareResult]:
        """Vergleicht eine einzelne Kategorie"""
        compare_methods = {
            'products': self._compare_products,
            'blogs': self._compare_blogs,
            'blog_posts': self._compare_blog_posts,
            'collections': self._compare_collections,
            'pages': self._compare_pages,
            'redirects': self._compare_redirects,
        }
        method = compare_methods.get(category)
        if method:
            return method()
        return []

    def _compare_products(self) -> List[CompareResult]:
        """Vergleicht Produkte"""
        results = []

        # Backup-Produkte laden
        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='product')
        }

        # Aktuelle Produkte von Shopify laden
        current_products = self._fetch_all_paginated('products.json', 'products')
        current_by_id = {p['id']: p for p in current_products}

        # Gelöschte und geänderte Produkte finden
        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_by_id:
                # Gelöscht
                results.append(CompareResult(
                    item_type='product',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                # Vergleichen
                current = current_by_id[shopify_id]
                backup_data = backup_item.raw_data
                changes = self._compare_product_data(backup_data, current)

                if changes:
                    results.append(CompareResult(
                        item_type='product',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        # Neue Produkte finden
        for shopify_id, current in current_by_id.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='product',
                    shopify_id=shopify_id,
                    title=current.get('title', 'Unbekannt'),
                    status='new',
                    current_data=current
                ))

        return results

    def _compare_product_data(self, backup: Dict, current: Dict) -> List[str]:
        """Vergleicht Produktdaten und gibt Liste der Änderungen zurück"""
        changes = []

        # Titel
        if backup.get('title') != current.get('title'):
            changes.append(f"Titel: '{backup.get('title')}' → '{current.get('title')}'")

        # Status
        if backup.get('status') != current.get('status'):
            changes.append(f"Status: {backup.get('status')} → {current.get('status')}")

        # Preis (erste Variante)
        backup_price = backup.get('variants', [{}])[0].get('price') if backup.get('variants') else None
        current_price = current.get('variants', [{}])[0].get('price') if current.get('variants') else None
        if backup_price != current_price:
            changes.append(f"Preis: {backup_price} → {current_price}")

        # Beschreibung (nur prüfen ob geändert, nicht den ganzen Text)
        if backup.get('body_html', '') != current.get('body_html', ''):
            changes.append("Beschreibung geändert")

        # Anzahl Bilder
        backup_images = len(backup.get('images', []))
        current_images = len(current.get('images', []))
        if backup_images != current_images:
            changes.append(f"Bilder: {backup_images} → {current_images}")

        # Tags
        if backup.get('tags', '') != current.get('tags', ''):
            changes.append("Tags geändert")

        return changes

    def _compare_blogs(self) -> List[CompareResult]:
        """Vergleicht Blogs"""
        results = []

        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='blog')
        }

        current_blogs = self._fetch_all_paginated('blogs.json', 'blogs')
        current_by_id = {b['id']: b for b in current_blogs}

        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_by_id:
                results.append(CompareResult(
                    item_type='blog',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                current = current_by_id[shopify_id]
                backup_data = backup_item.raw_data
                changes = []

                if backup_data.get('title') != current.get('title'):
                    changes.append(f"Titel: '{backup_data.get('title')}' → '{current.get('title')}'")

                if changes:
                    results.append(CompareResult(
                        item_type='blog',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        for shopify_id, current in current_by_id.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='blog',
                    shopify_id=shopify_id,
                    title=current.get('title', 'Unbekannt'),
                    status='new',
                    current_data=current
                ))

        return results

    def _compare_blog_posts(self) -> List[CompareResult]:
        """Vergleicht Blog-Posts"""
        results = []

        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='blog_post')
        }

        # Alle Posts von allen Blogs holen
        current_blogs = self._fetch_all_paginated('blogs.json', 'blogs')
        current_posts = {}

        for blog in current_blogs:
            articles = self._fetch_all_paginated(
                f'blogs/{blog["id"]}/articles.json', 'articles'
            )
            for article in articles:
                current_posts[article['id']] = article

        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_posts:
                results.append(CompareResult(
                    item_type='blog_post',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                current = current_posts[shopify_id]
                backup_data = backup_item.raw_data
                changes = []

                if backup_data.get('title') != current.get('title'):
                    changes.append(f"Titel: '{backup_data.get('title')}' → '{current.get('title')}'")

                if backup_data.get('body_html', '') != current.get('body_html', ''):
                    changes.append("Inhalt geändert")

                if backup_data.get('published') != current.get('published'):
                    changes.append(f"Veröffentlicht: {backup_data.get('published')} → {current.get('published')}")

                if changes:
                    results.append(CompareResult(
                        item_type='blog_post',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        for shopify_id, current in current_posts.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='blog_post',
                    shopify_id=shopify_id,
                    title=current.get('title', 'Unbekannt'),
                    status='new',
                    current_data=current
                ))

        return results

    def _compare_collections(self) -> List[CompareResult]:
        """Vergleicht Collections"""
        results = []

        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='collection')
        }

        # Custom und Smart Collections laden
        custom = self._fetch_all_paginated('custom_collections.json', 'custom_collections')
        smart = self._fetch_all_paginated('smart_collections.json', 'smart_collections')

        current_collections = {}
        for c in custom:
            c['collection_type'] = 'custom'
            current_collections[c['id']] = c
        for s in smart:
            s['collection_type'] = 'smart'
            current_collections[s['id']] = s

        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_collections:
                results.append(CompareResult(
                    item_type='collection',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                current = current_collections[shopify_id]
                backup_data = backup_item.raw_data
                changes = []

                if backup_data.get('title') != current.get('title'):
                    changes.append(f"Titel: '{backup_data.get('title')}' → '{current.get('title')}'")

                if backup_data.get('body_html', '') != current.get('body_html', ''):
                    changes.append("Beschreibung geändert")

                # Bild geändert
                backup_img = backup_data.get('image', {}).get('src', '') if backup_data.get('image') else ''
                current_img = current.get('image', {}).get('src', '') if current.get('image') else ''
                if backup_img != current_img:
                    changes.append("Bild geändert")

                if changes:
                    results.append(CompareResult(
                        item_type='collection',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        for shopify_id, current in current_collections.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='collection',
                    shopify_id=shopify_id,
                    title=current.get('title', 'Unbekannt'),
                    status='new',
                    current_data=current
                ))

        return results

    def _compare_pages(self) -> List[CompareResult]:
        """Vergleicht Seiten"""
        results = []

        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='page')
        }

        current_pages = self._fetch_all_paginated('pages.json', 'pages')
        current_by_id = {p['id']: p for p in current_pages}

        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_by_id:
                results.append(CompareResult(
                    item_type='page',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                current = current_by_id[shopify_id]
                backup_data = backup_item.raw_data
                changes = []

                if backup_data.get('title') != current.get('title'):
                    changes.append(f"Titel: '{backup_data.get('title')}' → '{current.get('title')}'")

                if backup_data.get('body_html', '') != current.get('body_html', ''):
                    changes.append("Inhalt geändert")

                if changes:
                    results.append(CompareResult(
                        item_type='page',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        for shopify_id, current in current_by_id.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='page',
                    shopify_id=shopify_id,
                    title=current.get('title', 'Unbekannt'),
                    status='new',
                    current_data=current
                ))

        return results

    def _compare_redirects(self) -> List[CompareResult]:
        """Vergleicht Redirects"""
        results = []

        backup_items = {
            item.shopify_id: item
            for item in self.backup.items.filter(item_type='redirect')
        }

        current_redirects = self._fetch_all_paginated('redirects.json', 'redirects')
        current_by_id = {r['id']: r for r in current_redirects}

        for shopify_id, backup_item in backup_items.items():
            if shopify_id not in current_by_id:
                results.append(CompareResult(
                    item_type='redirect',
                    shopify_id=shopify_id,
                    title=backup_item.title,
                    status='deleted',
                    backup_data=backup_item.raw_data,
                    backup_item_id=backup_item.id
                ))
            else:
                current = current_by_id[shopify_id]
                backup_data = backup_item.raw_data
                changes = []

                if backup_data.get('path') != current.get('path'):
                    changes.append(f"Pfad: '{backup_data.get('path')}' → '{current.get('path')}'")

                if backup_data.get('target') != current.get('target'):
                    changes.append(f"Ziel: '{backup_data.get('target')}' → '{current.get('target')}'")

                if changes:
                    results.append(CompareResult(
                        item_type='redirect',
                        shopify_id=shopify_id,
                        title=backup_item.title,
                        status='changed',
                        changes=changes,
                        backup_data=backup_data,
                        current_data=current,
                        backup_item_id=backup_item.id
                    ))

        for shopify_id, current in current_by_id.items():
            if shopify_id not in backup_items:
                results.append(CompareResult(
                    item_type='redirect',
                    shopify_id=shopify_id,
                    title=f"{current.get('path')} → {current.get('target')}",
                    status='new',
                    current_data=current
                ))

        return results

    def get_summary(self, results: Dict[str, List[CompareResult]]) -> Dict[str, Dict[str, int]]:
        """Erstellt eine Zusammenfassung der Vergleichsergebnisse"""
        summary = {}

        for category, items in results.items():
            summary[category] = {
                'deleted': sum(1 for i in items if i.status == 'deleted'),
                'new': sum(1 for i in items if i.status == 'new'),
                'changed': sum(1 for i in items if i.status == 'changed'),
                'total': len(items)
            }

        return summary

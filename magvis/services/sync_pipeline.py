"""Magvis Sync-Pipeline: importiert die im Run erstellten Shopify-Items in
die Workloom-shopify_manager-DB, damit sie unter /shopify/products/,
/shopify/collections/, /shopify/blogs/ direkt sichtbar/editierbar sind.

Wiederverwendung:
- shopify_manager.shopify_api.ShopifyAPIClient (fetch_product etc.)
- shopify_manager.shopify_api.ShopifyProductSync._create_or_update_product
- shopify_manager.shopify_api.ShopifyCollectionSync._create_or_update_collection
- shopify_manager.shopify_api.ShopifyBlogSync (für Blog/Article Import)
"""
from __future__ import annotations

import logging
from typing import Tuple

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisSyncPipeline:
    """Spiegelt die im Magvis-Run erzeugten Items in die shopify_manager-DB."""

    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user
        self.results = {
            'products': {'ok': 0, 'fail': 0, 'errors': []},
            'collection': {'ok': 0, 'fail': 0, 'errors': []},
            'blog': {'ok': 0, 'fail': 0, 'errors': []},
        }

    # ---------------------------------------------------------------- public

    def run(self) -> dict:
        store = self._get_shopify_manager_store()
        if not store:
            return {'success': False, 'error': 'Kein ShopifyStore in shopify_manager gefunden'}

        # 1) Produkte syncen
        self._sync_products(store)
        # 2) Kollektion syncen
        self._sync_collection(store)
        # 3) Blog syncen
        self._sync_blog(store)

        total_ok = sum(v['ok'] for v in self.results.values())
        total_fail = sum(v['fail'] for v in self.results.values())
        self.project.log_stage(
            'sync',
            f'🔄 Workloom-Sync: {total_ok} ok, {total_fail} fehlgeschlagen',
        )
        return {
            'success': total_fail == 0,
            'results': self.results,
            'total_ok': total_ok,
            'total_fail': total_fail,
        }

    # --------------------------------------------------------------- helpers

    def _get_shopify_manager_store(self):
        """Findet den ShopifyStore aus shopify_manager, der zum Magvis-Shop gehört.

        Strategie: matche über shop_domain mit dem ploom-Default-Store.
        """
        from ploom.models import PLoomSettings
        from shopify_manager.models import ShopifyStore as SMStore
        ps = PLoomSettings.objects.filter(user=self.user).first()
        if not ps or not ps.default_store:
            return None
        domain = ps.default_store.shop_domain
        return SMStore.objects.filter(user=self.user, shop_domain=domain).first()

    def _sync_products(self, store) -> None:
        """Importiert die 2 Magvis-Produkte in shopify_manager.ShopifyProduct."""
        from shopify_manager.shopify_api import ShopifyProductSync

        sync = ShopifyProductSync(store)
        for label, prod in [('1', self.project.product_1), ('2', self.project.product_2)]:
            if not prod or not prod.shopify_product_id:
                continue
            try:
                ok, product_data, msg = sync.api.fetch_product(str(prod.shopify_product_id))
                if not ok or not product_data:
                    self.results['products']['fail'] += 1
                    self.results['products']['errors'].append(
                        f'product_{label}: fetch fehlgeschlagen ({msg})')
                    continue
                sm_product, was_created = sync._create_or_update_product(
                    product_data, overwrite_existing=True, import_images=True,
                )
                self.results['products']['ok'] += 1
                self.project.log_stage(
                    'sync',
                    f'  ✓ Produkt {label}: shopify_manager-ID {sm_product.id} '
                    f'({"neu" if was_created else "aktualisiert"})',
                )
            except Exception as exc:
                logger.exception('Produkt-Sync %s', label)
                self.results['products']['fail'] += 1
                self.results['products']['errors'].append(f'product_{label}: {exc}')

    def _sync_collection(self, store) -> None:
        """Importiert die Magvis-Kollektion in shopify_manager.ShopifyCollection."""
        coll = getattr(self.project, 'collection', None)
        if not coll or not coll.shopify_collection_id:
            return
        from shopify_manager.shopify_api import ShopifyCollectionSync
        sync = ShopifyCollectionSync(store)
        try:
            # Direkter API-Call statt fetch_collections (Single-ID)
            collection_data = self._fetch_single_collection(store, coll.shopify_collection_id)
            if not collection_data:
                self.results['collection']['fail'] += 1
                self.results['collection']['errors'].append('collection: fetch fehlgeschlagen')
                return
            sm_coll, was_created = sync._create_or_update_collection(
                collection_data, overwrite_existing=True,
            )
            self.results['collection']['ok'] += 1
            self.project.log_stage(
                'sync',
                f'  ✓ Kollektion: shopify_manager-ID {sm_coll.id} '
                f'({"neu" if was_created else "aktualisiert"})',
            )
        except Exception as exc:
            logger.exception('Collection-Sync')
            self.results['collection']['fail'] += 1
            self.results['collection']['errors'].append(f'collection: {exc}')

    def _fetch_single_collection(self, store, collection_id: str) -> dict | None:
        """Holt eine Custom-Collection direkt per REST."""
        import requests
        h = {'X-Shopify-Access-Token': store.access_token}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        # Custom-Collection zuerst probieren, fallback Smart
        for endpoint in ('custom_collections', 'smart_collections', 'collections'):
            r = requests.get(f'{base}/{endpoint}/{collection_id}.json',
                             headers=h, timeout=20)
            if r.status_code == 200:
                key = endpoint.rstrip('s')  # custom_collection / smart_collection / collection
                # Versuche verschiedene Schlüssel
                for k in (key, 'collection', 'custom_collection', 'smart_collection'):
                    if k in r.json():
                        return r.json()[k]
        return None

    def _sync_blog(self, store) -> None:
        """Importiert Blog-Container + Article in shopify_manager.ShopifyBlog/-BlogPost."""
        blog = getattr(self.project, 'blog', None)
        if not blog or not blog.shopify_article_id:
            return
        from shopify_manager.shopify_api import ShopifyBlogSync
        sync = ShopifyBlogSync(store)
        try:
            # 1) Blog-Container syncen (sicherstellen dass er da ist)
            blog_data = self._fetch_single_blog(store, blog.shopify_blog_id) if blog.shopify_blog_id else None
            sm_blog = None
            if blog_data:
                sm_blog, was_blog_created = sync._create_or_update_blog(blog_data)
                self.project.log_stage(
                    'sync',
                    f'  ✓ Blog-Container: shopify_manager-ID {sm_blog.id} '
                    f'({"neu" if was_blog_created else "vorhanden"})',
                )

            # 2) Artikel syncen
            if not sm_blog:
                # Fallback: Blog-Container anhand Magvis-Daten finden
                from shopify_manager.models import ShopifyBlog as SMBlog
                sm_blog = SMBlog.objects.filter(
                    store=store, shopify_id=str(blog.shopify_blog_id),
                ).first()
            if not sm_blog:
                self.results['blog']['fail'] += 1
                self.results['blog']['errors'].append('blog: kein Blog-Container in shopify_manager')
                return
            article_data = self._fetch_single_article(
                store, blog.shopify_blog_id, blog.shopify_article_id,
            )
            if not article_data:
                self.results['blog']['fail'] += 1
                self.results['blog']['errors'].append('blog: article fetch fehlgeschlagen')
                return
            sm_post, was_created = sync._create_or_update_blog_post(sm_blog, article_data)
            self.results['blog']['ok'] += 1
            self.project.log_stage(
                'sync',
                f'  ✓ Blog-Artikel: shopify_manager-ID {sm_post.id} '
                f'({"neu" if was_created else "aktualisiert"})',
            )
        except Exception as exc:
            logger.exception('Blog-Sync')
            self.results['blog']['fail'] += 1
            self.results['blog']['errors'].append(f'blog: {exc}')

    def _fetch_single_blog(self, store, blog_id: str) -> dict | None:
        import requests
        if not blog_id:
            return None
        h = {'X-Shopify-Access-Token': store.access_token}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        r = requests.get(f'{base}/blogs/{blog_id}.json', headers=h, timeout=20)
        if r.status_code == 200:
            return r.json().get('blog')
        return None

    def _fetch_single_article(self, store, blog_id: str, article_id: str) -> dict | None:
        import requests
        if not blog_id or not article_id:
            return None
        h = {'X-Shopify-Access-Token': store.access_token}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        r = requests.get(f'{base}/blogs/{blog_id}/articles/{article_id}.json',
                         headers=h, timeout=20)
        if r.status_code == 200:
            return r.json().get('article')
        return None

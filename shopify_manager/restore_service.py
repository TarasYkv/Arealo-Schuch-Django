"""
Shopify Restore Service

Stellt Daten aus Backups wieder her:
- Einzelne Elemente oder ganze Kategorien
- Zwei Modi: "overwrite" oder "only_missing"
- Unterstützt alle Backup-Typen
"""

import requests
import json
import time
import base64
from typing import Dict, List, Optional, Tuple
from django.utils import timezone

from .models import ShopifyStore, ShopifyBackup, BackupItem, RestoreLog


class ShopifyRestoreService:
    """Service für die Wiederherstellung von Shopify-Daten"""

    RESTORE_MODES = ['overwrite', 'only_missing']

    def __init__(self, store: ShopifyStore, backup: ShopifyBackup, mode: str = 'only_missing'):
        self.store = store
        self.backup = backup
        self.mode = mode if mode in self.RESTORE_MODES else 'only_missing'
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
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Macht einen Rate-Limited API Request"""
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

    def _create_log(self, backup_item: BackupItem, status: str, message: str = '',
                    new_shopify_id: int = None) -> RestoreLog:
        """Erstellt einen Restore-Log-Eintrag"""
        return RestoreLog.objects.create(
            backup=self.backup,
            backup_item=backup_item,
            status=status,
            new_shopify_id=new_shopify_id,
            message=message
        )

    def restore_item(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt ein einzelnes Element wieder her"""
        item_type = backup_item.item_type

        restore_methods = {
            'product': self._restore_product,
            'blog': self._restore_blog,
            'blog_post': self._restore_blog_post,
            'collection': self._restore_collection,
            'page': self._restore_page,
            'redirect': self._restore_redirect,
            'metafield': self._restore_metafield,
            'discount': self._restore_discount,
            # Orders und Customers können nicht erstellt werden
            'order': self._skip_restore,
            'customer': self._skip_restore,
            'product_image': self._skip_restore,
            'blog_image': self._skip_restore,
        }

        method = restore_methods.get(item_type, self._skip_restore)
        return method(backup_item)

    def restore_category(self, item_type: str) -> List[RestoreLog]:
        """Stellt alle Elemente einer Kategorie wieder her"""
        items = self.backup.items.filter(item_type=item_type)
        logs = []

        for item in items:
            log = self.restore_item(item)
            logs.append(log)

        return logs

    def restore_all(self) -> Dict[str, List[RestoreLog]]:
        """Stellt alle wiederherstellbaren Elemente wieder her"""
        results = {}

        # Reihenfolge ist wichtig: z.B. Blogs vor Blog-Posts
        restore_order = [
            'blog',
            'collection',
            'page',
            'redirect',
            'metafield',
            'discount',
            'product',
            'blog_post',  # Nach Blogs
        ]

        for item_type in restore_order:
            items = self.backup.items.filter(item_type=item_type)
            if items.exists():
                results[item_type] = self.restore_category(item_type)

        return results

    def _skip_restore(self, backup_item: BackupItem) -> RestoreLog:
        """Überspringt nicht-wiederherstellbare Elemente"""
        return self._create_log(
            backup_item,
            'skipped',
            f'{backup_item.get_item_type_display()} kann nicht wiederhergestellt werden'
        )

    def _get_image_attachment(self, backup_item: BackupItem) -> Optional[str]:
        """Konvertiert gespeicherte Bilddaten zu base64 für Shopify API"""
        if backup_item.image_path:
            try:
                image_data = backup_item.get_image_data()
                if image_data:
                    return base64.b64encode(image_data).decode('utf-8')
            except:
                pass
        return None

    def _check_exists_by_handle(self, endpoint: str, handle: str) -> Optional[int]:
        """Prüft ob ein Element mit diesem Handle existiert"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/{endpoint}",
                params={'handle': handle},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                # Der Key hängt vom Endpoint ab
                key = endpoint.replace('.json', '')
                items = data.get(key, [])
                if items:
                    return items[0]['id']
        except:
            pass
        return None

    def _restore_product(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt ein Produkt wieder her (mit lokal gespeicherten Bildern)"""
        data = backup_item.raw_data

        # Prüfen ob Produkt existiert (via Handle)
        if self.mode == 'only_missing':
            existing_id = self._check_exists_by_handle('products.json', data.get('handle', ''))
            if existing_id:
                return self._create_log(backup_item, 'exists', 'Produkt existiert bereits', existing_id)

        # Produkt-Daten für API vorbereiten
        product_data = {
            'product': {
                'title': data.get('title'),
                'body_html': data.get('body_html', ''),
                'vendor': data.get('vendor', ''),
                'product_type': data.get('product_type', ''),
                'tags': data.get('tags', ''),
                'status': data.get('status', 'draft'),
            }
        }

        # Varianten hinzufügen
        if data.get('variants'):
            product_data['product']['variants'] = []
            for variant in data['variants']:
                product_data['product']['variants'].append({
                    'title': variant.get('title'),
                    'price': variant.get('price'),
                    'sku': variant.get('sku'),
                    'compare_at_price': variant.get('compare_at_price'),
                    'inventory_management': variant.get('inventory_management'),
                    'weight': variant.get('weight'),
                    'weight_unit': variant.get('weight_unit'),
                })

        # Bilder hinzufügen - bevorzuge lokale Daten aus product_image Items
        images_added = 0
        if data.get('images'):
            product_data['product']['images'] = []

            # Hole alle lokal gespeicherten Produktbilder für dieses Produkt
            product_images = self.backup.items.filter(
                item_type='product_image',
                parent_id=backup_item.shopify_id
            )
            local_images = {img.shopify_id: img for img in product_images if img.image_path}

            for img in data['images']:
                img_id = img.get('id')
                img_data = {}

                # Prüfe ob wir lokale Bilddaten haben
                if img_id and img_id in local_images:
                    local_img = local_images[img_id]
                    try:
                        image_bytes = local_img.get_image_data()
                        if image_bytes:
                            attachment = base64.b64encode(image_bytes).decode('utf-8')
                            img_data['attachment'] = attachment
                            img_data['alt'] = img.get('alt', '')
                            images_added += 1
                        else:
                            # Fallback auf URL
                            img_data['src'] = img.get('src')
                            img_data['alt'] = img.get('alt', '')
                    except:
                        # Fallback auf URL
                        img_data['src'] = img.get('src')
                        img_data['alt'] = img.get('alt', '')
                else:
                    # Fallback auf externe URL
                    img_data['src'] = img.get('src')
                    img_data['alt'] = img.get('alt', '')

                product_data['product']['images'].append(img_data)

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/products.json",
                json=product_data,
                timeout=120  # Längerer Timeout für große Bilder
            )

            if response.status_code == 201:
                new_product = response.json().get('product', {})
                msg = 'Produkt erfolgreich wiederhergestellt'
                if images_added > 0:
                    msg += f' ({images_added} lokale Bilder)'
                return self._create_log(
                    backup_item,
                    'success',
                    msg,
                    new_product.get('id')
                )
            elif response.status_code == 422 and 'image' in response.text.lower():
                # Bild-Fehler - Retry ohne Bilder
                if 'images' in product_data['product']:
                    del product_data['product']['images']
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/products.json",
                    json=product_data,
                    timeout=60
                )
                if response.status_code == 201:
                    new_product = response.json().get('product', {})
                    return self._create_log(
                        backup_item,
                        'success',
                        'Produkt wiederhergestellt (ohne Bilder)',
                        new_product.get('id')
                    )
                else:
                    return self._create_log(
                        backup_item,
                        'failed',
                        f'API-Fehler: {response.status_code} - {response.text[:500]}'
                    )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_blog(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt einen Blog wieder her"""
        data = backup_item.raw_data

        # Prüfen ob Blog existiert
        if self.mode == 'only_missing':
            existing_id = self._check_exists_by_handle('blogs.json', data.get('handle', ''))
            if existing_id:
                return self._create_log(backup_item, 'exists', 'Blog existiert bereits', existing_id)

        blog_data = {
            'blog': {
                'title': data.get('title'),
                'handle': data.get('handle'),
            }
        }

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/blogs.json",
                json=blog_data,
                timeout=30
            )

            if response.status_code == 201:
                new_blog = response.json().get('blog', {})
                return self._create_log(
                    backup_item,
                    'success',
                    'Blog erfolgreich wiederhergestellt',
                    new_blog.get('id')
                )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_blog_post(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt einen Blog-Post wieder her (mit lokal gespeicherten Bildern)"""
        data = backup_item.raw_data
        blog_id = backup_item.parent_id

        if not blog_id:
            return self._create_log(backup_item, 'failed', 'Keine Blog-ID vorhanden')

        # Prüfen ob der Blog existiert
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}.json",
                timeout=30
            )
            if response.status_code != 200:
                # Blog existiert nicht mehr, versuche Blog mit gleichem Handle zu finden
                return self._create_log(backup_item, 'failed', 'Zugehöriger Blog existiert nicht')
        except:
            return self._create_log(backup_item, 'failed', 'Zugehöriger Blog konnte nicht geprüft werden')

        article_data = {
            'article': {
                'title': data.get('title'),
                'body_html': data.get('body_html', ''),
                'author': data.get('author', ''),
                'tags': data.get('tags', ''),
                'summary_html': data.get('summary_html', ''),
                'published': data.get('published', False),
            }
        }

        # Bild hinzufügen - bevorzuge lokale Daten, fallback auf URL
        has_image = False
        image_attachment = self._get_image_attachment(backup_item)
        if image_attachment:
            # Lokales Bild als base64
            article_data['article']['image'] = {
                'attachment': image_attachment,
                'alt': data.get('image', {}).get('alt', '')
            }
            has_image = True
        elif data.get('image') and data['image'].get('src'):
            # Fallback auf externe URL
            article_data['article']['image'] = {
                'src': data['image']['src'],
                'alt': data['image'].get('alt', '')
            }
            has_image = True

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                json=article_data,
                timeout=30
            )

            if response.status_code == 201:
                new_article = response.json().get('article', {})
                msg = 'Blog-Post erfolgreich wiederhergestellt'
                if image_attachment:
                    msg += ' (mit lokalem Bild)'
                return self._create_log(
                    backup_item,
                    'success',
                    msg,
                    new_article.get('id')
                )
            elif response.status_code == 422 and has_image and 'image' in response.text.lower():
                # Bild-Fehler - Retry ohne Bild
                del article_data['article']['image']
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/blogs/{blog_id}/articles.json",
                    json=article_data,
                    timeout=30
                )
                if response.status_code == 201:
                    new_article = response.json().get('article', {})
                    return self._create_log(
                        backup_item,
                        'success',
                        'Blog-Post wiederhergestellt (ohne Bild)',
                        new_article.get('id')
                    )
                else:
                    return self._create_log(
                        backup_item,
                        'failed',
                        f'API-Fehler: {response.status_code} - {response.text[:500]}'
                    )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_collection(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt eine Collection wieder her (mit lokal gespeicherten Bildern)"""
        data = backup_item.raw_data
        collection_type = data.get('collection_type', 'custom')

        # Endpoint basierend auf Typ
        if collection_type == 'smart':
            endpoint = 'smart_collections.json'
            key = 'smart_collection'
        else:
            endpoint = 'custom_collections.json'
            key = 'custom_collection'

        # Prüfen ob Collection existiert
        if self.mode == 'only_missing':
            existing_id = self._check_exists_by_handle(
                'custom_collections.json' if collection_type == 'custom' else 'smart_collections.json',
                data.get('handle', '')
            )
            if existing_id:
                return self._create_log(backup_item, 'exists', 'Collection existiert bereits', existing_id)

        collection_data = {
            key: {
                'title': data.get('title'),
                'body_html': data.get('body_html', ''),
                'published': data.get('published', True),
            }
        }

        # Bild hinzufügen - bevorzuge lokale Daten, fallback auf URL
        has_image = False
        image_attachment = self._get_image_attachment(backup_item)
        if image_attachment:
            # Lokales Bild als base64
            collection_data[key]['image'] = {
                'attachment': image_attachment,
                'alt': data.get('image', {}).get('alt', '')
            }
            has_image = True
        elif data.get('image') and data['image'].get('src'):
            # Fallback auf externe URL
            collection_data[key]['image'] = {
                'src': data['image']['src'],
                'alt': data['image'].get('alt', '')
            }
            has_image = True

        # Smart Collection Rules
        if collection_type == 'smart' and data.get('rules'):
            collection_data[key]['rules'] = data['rules']
            collection_data[key]['disjunctive'] = data.get('disjunctive', False)

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/{endpoint}",
                json=collection_data,
                timeout=30
            )

            if response.status_code == 201:
                new_collection = response.json().get(key, {})
                msg = 'Collection erfolgreich wiederhergestellt'
                if image_attachment:
                    msg += ' (mit lokalem Bild)'
                return self._create_log(
                    backup_item,
                    'success',
                    msg,
                    new_collection.get('id')
                )
            elif response.status_code == 422 and has_image and 'image' in response.text.lower():
                # Bild-Fehler - Retry ohne Bild
                del collection_data[key]['image']
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/{endpoint}",
                    json=collection_data,
                    timeout=30
                )
                if response.status_code == 201:
                    new_collection = response.json().get(key, {})
                    return self._create_log(
                        backup_item,
                        'success',
                        'Collection wiederhergestellt (ohne Bild)',
                        new_collection.get('id')
                    )
                else:
                    return self._create_log(
                        backup_item,
                        'failed',
                        f'API-Fehler: {response.status_code} - {response.text[:500]}'
                    )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_page(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt eine statische Seite wieder her"""
        data = backup_item.raw_data

        # Prüfen ob Page existiert
        if self.mode == 'only_missing':
            existing_id = self._check_exists_by_handle('pages.json', data.get('handle', ''))
            if existing_id:
                return self._create_log(backup_item, 'exists', 'Seite existiert bereits', existing_id)

        page_data = {
            'page': {
                'title': data.get('title'),
                'body_html': data.get('body_html', ''),
                'published': data.get('published', True),
            }
        }

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/pages.json",
                json=page_data,
                timeout=30
            )

            if response.status_code == 201:
                new_page = response.json().get('page', {})
                return self._create_log(
                    backup_item,
                    'success',
                    'Seite erfolgreich wiederhergestellt',
                    new_page.get('id')
                )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_redirect(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt eine URL-Weiterleitung wieder her"""
        data = backup_item.raw_data

        # Prüfen ob Redirect existiert (via path)
        if self.mode == 'only_missing':
            try:
                response = self._make_request(
                    'GET',
                    f"{self.base_url}/redirects.json",
                    params={'path': data.get('path', '')},
                    timeout=30
                )
                if response.status_code == 200:
                    redirects = response.json().get('redirects', [])
                    if redirects:
                        return self._create_log(
                            backup_item, 'exists',
                            'Redirect existiert bereits',
                            redirects[0]['id']
                        )
            except:
                pass

        redirect_data = {
            'redirect': {
                'path': data.get('path'),
                'target': data.get('target'),
            }
        }

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/redirects.json",
                json=redirect_data,
                timeout=30
            )

            if response.status_code == 201:
                new_redirect = response.json().get('redirect', {})
                return self._create_log(
                    backup_item,
                    'success',
                    'Redirect erfolgreich wiederhergestellt',
                    new_redirect.get('id')
                )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_metafield(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt ein Metafield wieder her"""
        data = backup_item.raw_data

        metafield_data = {
            'metafield': {
                'namespace': data.get('namespace'),
                'key': data.get('key'),
                'value': data.get('value'),
                'type': data.get('type', 'single_line_text_field'),
            }
        }

        try:
            response = self._make_request(
                'POST',
                f"{self.base_url}/metafields.json",
                json=metafield_data,
                timeout=30
            )

            if response.status_code == 201:
                new_mf = response.json().get('metafield', {})
                return self._create_log(
                    backup_item,
                    'success',
                    'Metafield erfolgreich wiederhergestellt',
                    new_mf.get('id')
                )
            elif response.status_code == 422:
                # Metafield existiert möglicherweise bereits
                return self._create_log(backup_item, 'exists', 'Metafield existiert möglicherweise bereits')
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'API-Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

    def _restore_discount(self, backup_item: BackupItem) -> RestoreLog:
        """Stellt einen Rabattcode wieder her"""
        data = backup_item.raw_data
        price_rule = data.get('price_rule', {})

        if not price_rule:
            return self._create_log(backup_item, 'failed', 'Keine Price Rule-Daten vorhanden')

        # Erst Price Rule erstellen
        price_rule_data = {
            'price_rule': {
                'title': price_rule.get('title'),
                'target_type': price_rule.get('target_type', 'line_item'),
                'target_selection': price_rule.get('target_selection', 'all'),
                'allocation_method': price_rule.get('allocation_method', 'across'),
                'value_type': price_rule.get('value_type', 'percentage'),
                'value': price_rule.get('value', '-10.0'),
                'customer_selection': price_rule.get('customer_selection', 'all'),
                'starts_at': price_rule.get('starts_at'),
            }
        }

        try:
            # Price Rule erstellen
            response = self._make_request(
                'POST',
                f"{self.base_url}/price_rules.json",
                json=price_rule_data,
                timeout=30
            )

            if response.status_code != 201:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'Price Rule Fehler: {response.status_code} - {response.text[:500]}'
                )

            new_rule_id = response.json().get('price_rule', {}).get('id')

            # Discount Code erstellen
            discount_code_data = {
                'discount_code': {
                    'code': data.get('code')
                }
            }

            response = self._make_request(
                'POST',
                f"{self.base_url}/price_rules/{new_rule_id}/discount_codes.json",
                json=discount_code_data,
                timeout=30
            )

            if response.status_code == 201:
                new_code = response.json().get('discount_code', {})
                return self._create_log(
                    backup_item,
                    'success',
                    'Rabattcode erfolgreich wiederhergestellt',
                    new_code.get('id')
                )
            else:
                return self._create_log(
                    backup_item,
                    'failed',
                    f'Discount Code Fehler: {response.status_code} - {response.text[:500]}'
                )
        except Exception as e:
            return self._create_log(backup_item, 'failed', f'Fehler: {str(e)}')

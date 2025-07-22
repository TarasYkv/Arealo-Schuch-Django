import requests
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from django.utils import timezone as django_timezone
from django.db import models
from .models import ShopifyStore, ShopifyProduct, ShopifyProductImage, ShopifySyncLog, ShopifyBlog, ShopifyBlogPost, ShopifyCollection


class ShopifyAPIClient:
    """Shopify API Client für Produktverwaltung"""
    
    def __init__(self, store: ShopifyStore):
        self.store = store
        self.base_url = store.get_api_url()
        self.headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json'
        }
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms zwischen Requests = 2 Requests pro Sekunde
    
    def _rate_limit(self):
        """Wartet die minimale Zeit zwischen API-Requests ab"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            print(f"⏱️ Rate limiting: Warte {sleep_time:.2f}s...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Macht einen Rate-Limited API Request mit Retry-Logik"""
        max_retries = 3
        retry_delay = 1.0  # Startet mit 1 Sekunde
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = requests.request(method, url, headers=self.headers, **kwargs)
                
                # Prüfe auf Rate-Limiting
                if response.status_code == 429:
                    print(f"⚠️ Rate limit erreicht (Versuch {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        print(f"⏳ Warte {retry_delay}s vor erneutem Versuch...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Request-Fehler (Versuch {attempt + 1}/{max_retries}): {e}")
                    print(f"⏳ Warte {retry_delay}s vor erneutem Versuch...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise
        
        return response
    
    def test_connection(self) -> Tuple[bool, str]:
        """Testet die Verbindung zur Shopify API"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/shop.json",
                timeout=10
            )
            
            if response.status_code == 200:
                shop_data = response.json()
                shop_name = shop_data.get('shop', {}).get('name', 'Unbekannt')
                return True, f"Verbindung erfolgreich zu Shop: {shop_name}"
            elif response.status_code == 401:
                return False, "Ungültiger Access Token"
            elif response.status_code == 403:
                return False, "Keine Berechtigung für diese API"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Verbindungsfehler: {str(e)}"
    
    def fetch_products(self, limit: int = 250, since_id: Optional[str] = None) -> Tuple[bool, List[Dict], str]:
        """Holt Produkte von Shopify API"""
        try:
            params = {
                'limit': min(limit, 250),  # Shopify maximum
                'fields': 'id,title,handle,body_html,vendor,product_type,status,seo_title,seo_description,images,variants,tags,created_at,updated_at'
            }
            
            if since_id:
                params['since_id'] = since_id
            
            response = self._make_request(
                'GET',
                f"{self.base_url}/products.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                return True, products, f"{len(products)} Produkte abgerufen"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen: {str(e)}"
    
    def fetch_collections(self, limit: int = 250, since_id: Optional[str] = None) -> Tuple[bool, List[Dict], str]:
        """Holt Collections (Kategorien) von Shopify API"""
        try:
            params = {
                'limit': min(limit, 250),  # Shopify maximum
                'fields': 'id,title,handle,body_html,published,image,seo_title,seo_description,sort_order,created_at,updated_at'
            }
            
            if since_id:
                params['since_id'] = since_id
            
            # Shopify hat zwei Collection-Typen: custom_collections und smart_collections
            # Wir holen beide und kombinieren sie
            all_collections = []
            
            # Custom Collections
            response = self._make_request(
                'GET',
                f"{self.base_url}/custom_collections.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                custom_collections = data.get('custom_collections', [])
                # Füge collection_type hinzu
                for collection in custom_collections:
                    collection['collection_type'] = 'custom'
                all_collections.extend(custom_collections)
            elif response.status_code != 404:  # 404 ist OK wenn keine custom collections existieren
                return False, [], f"Fehler bei custom_collections: HTTP {response.status_code}: {response.text}"
            
            # Smart Collections
            response = self._make_request(
                'GET',
                f"{self.base_url}/smart_collections.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                smart_collections = data.get('smart_collections', [])
                # Füge collection_type hinzu
                for collection in smart_collections:
                    collection['collection_type'] = 'smart'
                all_collections.extend(smart_collections)
            elif response.status_code != 404:  # 404 ist OK wenn keine smart collections existieren
                return False, [], f"Fehler bei smart_collections: HTTP {response.status_code}: {response.text}"
            
            return True, all_collections, f"{len(all_collections)} Collections abgerufen"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Collections: {str(e)}"
    
    def search_products(self, search_term: str, limit: int = 50) -> Tuple[bool, List[Dict], str]:
        """Sucht Produkte nach Name/Titel"""
        try:
            params = {
                'limit': min(limit, 250),  # Shopify maximum
                'fields': 'id,title,handle,body_html,vendor,product_type,status,seo_title,seo_description,images,variants,tags,created_at,updated_at',
                'title': search_term  # Shopify API unterstützt Titel-Suche
            }
            
            response = self._make_request(
                'GET',
                f"{self.base_url}/products.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                
                # Zusätzliche clientseitige Filterung für bessere Übereinstimmung
                filtered_products = []
                search_lower = search_term.lower()
                for product in products:
                    title = product.get('title', '').lower()
                    if search_lower in title:
                        filtered_products.append(product)
                
                return True, filtered_products, f"{len(filtered_products)} Produkte gefunden"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler bei der Suche: {str(e)}"
    
    def fetch_product(self, product_id: str) -> Tuple[bool, Optional[Dict], str]:
        """Holt ein einzelnes Produkt von Shopify"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/products/{product_id}.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                product = data.get('product')
                return True, product, "Produkt erfolgreich abgerufen"
            elif response.status_code == 404:
                return False, None, "Produkt nicht gefunden"
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Abrufen: {str(e)}"
    
    def update_product(self, product_id: str, product_data: Dict) -> Tuple[bool, Optional[Dict], str]:
        """Aktualisiert ein Produkt in Shopify"""
        try:
            # 1. Erst die Standard-Produktdaten aktualisieren
            shopify_data = {
                'product': {
                    'id': int(product_id),
                    'title': product_data.get('title'),
                    'body_html': product_data.get('body_html'),
                    'vendor': product_data.get('vendor'),
                    'product_type': product_data.get('product_type'),
                    'status': product_data.get('status'),
                    'tags': product_data.get('tags'),
                }
            }
            
            response = self._make_request(
                'PUT',
                f"{self.base_url}/products/{product_id}.json",
                json=shopify_data,
                timeout=15
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Produkt-Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
            
            data = response.json()
            updated_product = data.get('product')
            
            # 2. SEO-Daten über separate Metafields API aktualisieren
            seo_success = True
            seo_messages = []
            
            if 'seo_title' in product_data and product_data.get('seo_title'):
                success, message = self.update_product_metafield(
                    product_id, 'global', 'title_tag', 
                    product_data['seo_title'], 'single_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Titel aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Titel Fehler: {message}")
            
            if 'seo_description' in product_data and product_data.get('seo_description'):
                success, message = self.update_product_metafield(
                    product_id, 'global', 'description_tag', 
                    product_data['seo_description'], 'multi_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Beschreibung aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Beschreibung Fehler: {message}")
            
            # Kombiniere Ergebnisse
            final_message = "Produkt erfolgreich aktualisiert"
            if seo_messages:
                final_message += ". " + "; ".join(seo_messages)
            
            return seo_success, updated_product, final_message
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Update: {str(e)}"

    def update_product_seo_only(self, product_id: str, seo_title: str = None, seo_description: str = None) -> Tuple[bool, str]:
        """Aktualisiert nur die SEO-Metafelder eines Produkts ohne andere Felder zu ändern"""
        seo_success = True
        seo_messages = []
        
        try:
            if seo_title:
                success, message = self.update_product_metafield(
                    product_id, 'global', 'title_tag', 
                    seo_title, 'single_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Titel aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Titel Fehler: {message}")
            
            if seo_description:
                success, message = self.update_product_metafield(
                    product_id, 'global', 'description_tag', 
                    seo_description, 'single_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Beschreibung aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Beschreibung Fehler: {message}")
            
            final_message = "SEO-Daten aktualisiert"
            if seo_messages:
                final_message = "; ".join(seo_messages)
            
            return seo_success, final_message
            
        except Exception as e:
            return False, f"Fehler beim SEO-Update: {str(e)}"

    def update_product_metafield(self, product_id: str, namespace: str, key: str, value: str, field_type: str) -> Tuple[bool, str]:
        """Aktualisiert oder erstellt ein spezifisches Metafield für ein Produkt"""
        try:
            # Erst prüfen, ob das Metafield bereits existiert
            success, metafields, message = self.get_product_metafields(product_id)
            existing_metafield_id = None
            
            if success:
                for mf in metafields:
                    if isinstance(mf, dict) and mf.get('namespace') == namespace and mf.get('key') == key:
                        existing_metafield_id = mf.get('id')
                        break
            
            metafield_data = {
                'metafield': {
                    'namespace': namespace,
                    'key': key,
                    'value': value,
                    'type': field_type
                }
            }
            
            if existing_metafield_id:
                # Update existing metafield
                metafield_data['metafield']['id'] = existing_metafield_id
                response = self._make_request(
                    'PUT',
                    f"{self.base_url}/products/{product_id}/metafields/{existing_metafield_id}.json",
                    json=metafield_data,
                    timeout=10
                )
            else:
                # Create new metafield
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/products/{product_id}/metafields.json",
                    json=metafield_data,
                    timeout=10
                )
            
            if response.status_code in [200, 201]:
                return True, f"Metafield {namespace}.{key} erfolgreich {'aktualisiert' if existing_metafield_id else 'erstellt'}"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, f"HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Fehler beim Metafield-Update: {str(e)}"
    
    def get_product_metafields(self, product_id: str) -> Tuple[bool, List[Dict], str]:
        """Holt Metafields eines Produkts (für SEO Daten)"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/products/{product_id}/metafields.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                metafields = data.get('metafields', [])
                return True, metafields, f"{len(metafields)} Metafields gefunden"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Metafields: {str(e)}"

    def search_webrex_seo_data(self, product_id: str) -> Tuple[bool, Dict, str]:
        """Spezialisierte Suche nach Webrex SEO-Daten mit erweiterten Strategien"""
        try:
            # Strategie 1: Standard Metafields
            meta_success, metafields, meta_message = self.get_product_metafields(product_id)
            
            result = {
                'metafields_found': len(metafields) if meta_success else 0,
                'webrex_fields': [],
                'potential_seo_fields': [],
                'all_namespaces': set(),
                'search_strategies': []
            }
            
            if meta_success and metafields:
                for mf in metafields:
                    if isinstance(mf, dict):
                        namespace = mf.get('namespace', '').lower()
                        key = mf.get('key', '').lower()
                        value = str(mf.get('value', ''))
                        
                        result['all_namespaces'].add(namespace)
                        
                        # Erweiterte Webrex-Erkennung
                        if any(term in namespace for term in ['webrex', 'breadcrumb', 'schema', 'seo']):
                            result['webrex_fields'].append({
                                'namespace': mf.get('namespace', ''),
                                'key': mf.get('key', ''),
                                'value': value,
                                'type': mf.get('type', ''),
                                'description': mf.get('description', '')
                            })
                        
                        # Potentielle SEO-Felder
                        if any(seo_term in (namespace + key) for seo_term in ['title', 'description', 'meta', 'seo']):
                            result['potential_seo_fields'].append({
                                'namespace': mf.get('namespace', ''),
                                'key': mf.get('key', ''),
                                'value': value[:200],  # Begrenzte Vorschau
                                'type': mf.get('type', '')
                            })
            
            result['search_strategies'].append(f"Standard Metafields: {result['metafields_found']} gefunden")
            
            # Strategie 2: Versuche alternative Endpunkte für Webrex
            # (Diese könnten existieren, falls Webrex eigene API-Endpunkte verwendet)
            
            # Konvertiere Set zu Liste für JSON-Serialisierung
            result['all_namespaces'] = list(result['all_namespaces'])
            
            return True, result, f"Webrex-Suche abgeschlossen: {len(result['webrex_fields'])} Webrex-Felder, {len(result['potential_seo_fields'])} SEO-Felder gefunden"
            
        except Exception as e:
            return False, {}, f"Fehler bei Webrex-Suche: {str(e)}"

    def get_product(self, product_id: str) -> Tuple[bool, Dict, str]:
        """Holt ein einzelnes Produkt von Shopify"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/products/{product_id}.json",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                product = data.get('product', {})
                return True, product, "Produkt erfolgreich abgerufen"
            else:
                return False, {}, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, {}, f"Fehler beim Abrufen des Produkts: {str(e)}"
    
    def update_product_images(self, product_id: str, images: List[Dict]) -> Tuple[bool, Optional[Dict], str]:
        """Aktualisiert die Bilder eines Produkts in Shopify"""
        try:
            # Bereite Bilder-Daten für Shopify vor
            shopify_images = []
            for img in images:
                shopify_img = {}
                
                # ID ist erforderlich für Updates bestehender Bilder
                if 'id' in img and img['id']:
                    shopify_img['id'] = int(img['id'])
                
                # Alt-Text ist das wichtigste Feld
                if 'alt' in img:
                    shopify_img['alt'] = str(img['alt'])[:512]  # Shopify Alt-Text Limit
                
                # Position falls vorhanden
                if 'position' in img:
                    shopify_img['position'] = int(img['position'])
                
                # Weitere Felder falls vorhanden
                for field in ['src', 'filename', 'attachment', 'width', 'height']:
                    if field in img and img[field]:
                        shopify_img[field] = img[field]
                
                shopify_images.append(shopify_img)
                print(f"DEBUG: Bild für Sync vorbereitet - ID: {shopify_img.get('id', 'N/A')}, Alt: '{shopify_img.get('alt', '')[:50]}...', Position: {shopify_img.get('position', 'N/A')}")
            
            shopify_data = {
                'product': {
                    'id': int(product_id),
                    'images': shopify_images
                }
            }
            
            print(f"DEBUG: Sende {len(shopify_images)} Bilder an Shopify für Produkt {product_id}")
            
            response = self._make_request(
                'PUT',
                f"{self.base_url}/products/{product_id}.json",
                json=shopify_data,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                updated_product = data.get('product')
                updated_images = updated_product.get('images', []) if updated_product else []
                print(f"DEBUG: Shopify hat {len(updated_images)} Bilder zurückgegeben")
                return True, updated_product, f"Produktbilder erfolgreich aktualisiert ({len(updated_images)} Bilder)"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                print(f"DEBUG: Shopify Bilder-Update Fehler - Status: {response.status_code}, Error: {error_data}")
                return False, None, f"Bilder-Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request Exception bei Bilder-Update: {str(e)}")
            return False, None, f"Fehler beim Update der Bilder: {str(e)}"
    
    def update_single_product_image(self, product_id: str, image_id: str, alt_text: str) -> Tuple[bool, str]:
        """Aktualisiert ein einzelnes Produktbild in Shopify"""
        try:
            image_data = {
                'image': {
                    'id': int(image_id),
                    'alt': str(alt_text)[:512]  # Shopify Alt-Text Limit
                }
            }
            
            print(f"DEBUG: Aktualisiere einzelnes Bild {image_id} für Produkt {product_id} mit Alt-Text: '{alt_text[:50]}...'")
            
            response = self._make_request(
                'PUT',
                f"{self.base_url}/products/{product_id}/images/{image_id}.json",
                json=image_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                updated_image = data.get('image')
                print(f"DEBUG: Einzelbild-Update erfolgreich - ID: {updated_image.get('id') if updated_image else 'N/A'}")
                return True, "Einzelnes Bild erfolgreich aktualisiert"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                print(f"DEBUG: Einzelbild-Update Fehler - Status: {response.status_code}, Error: {error_data}")
                return False, f"Einzelbild-Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request Exception bei Einzelbild-Update: {str(e)}")
            return False, f"Fehler beim Update des einzelnen Bildes: {str(e)}"
    
    def fetch_blogs(self) -> Tuple[bool, List[Dict], str]:
        """Holt Blogs von Shopify API"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs.json",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                blogs = data.get('blogs', [])
                return True, blogs, f"{len(blogs)} Blogs abgerufen"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Blogs: {str(e)}"
    
    def fetch_blog_posts(self, blog_id: str, limit: int = 250, page_info: Optional[str] = None, fields: Optional[str] = None) -> Tuple[bool, List[Dict], str, Optional[str]]:
        """
        Holt Blog-Posts für einen bestimmten Blog mit moderner cursor-basierter Pagination
        
        Returns:
            Tuple[bool, List[Dict], str, Optional[str]]: success, articles, message, next_page_info
        """
        try:
            # Basis-Parameter für cursor-basierte Pagination
            if fields:
                params = {
                    'limit': min(limit, 250),
                    'fields': fields
                }
            else:
                params = {
                    'limit': min(limit, 250),
                    'fields': 'id,title,handle,author,status,created_at,updated_at,published_at,tags,image,body_html,summary'
                }
            
            # MODERNE PAGINATION: Verwende page_info statt veraltete Parameter
            if page_info:
                params['page_info'] = page_info
                print(f"📄 API-Call mit page_info cursor")
            
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                # Parse Link-Header für nächste Seite
                next_page_info = self._parse_link_header_for_next_page(response.headers.get('Link', ''))
                
                # Erweitere Artikel nur um fehlende Felder wenn nötig
                enhanced_articles = []
                for article in articles:
                    # Prüfe ob wichtige Felder fehlen
                    body_html = article.get('body_html', '')
                    summary = article.get('summary', '')
                    
                    # Nur wenn beide Felder leer sind, hole vollständige Daten
                    if not body_html and not summary:
                        article_id = article.get('id')
                        if article_id:
                            print(f"⚠️ Hole vollständige Daten für Artikel {article_id} (Content fehlt)")
                            full_success, full_article, full_message = self.fetch_single_blog_post(blog_id, str(article_id))
                            if full_success and full_article:
                                article.update(full_article)
                    
                    enhanced_articles.append(article)
                
                return True, enhanced_articles, f"{len(enhanced_articles)} Blog-Posts abgerufen", next_page_info
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}", None
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Blog-Posts: {str(e)}", None
    
    def _parse_link_header_for_next_page(self, link_header: str) -> Optional[str]:
        """
        Parst den Link-Header der Shopify API um den page_info für die nächste Seite zu extrahieren
        
        Link-Header Format:
        <https://store.myshopify.com/admin/api/2024-01/blogs/123/articles.json?page_info=XXXXX&limit=250>; rel="next"
        """
        if not link_header:
            return None
            
        try:
            import re
            # Suche nach dem "next" Link im Link-Header
            next_link_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
            
            if next_link_match:
                next_url = next_link_match.group(1)
                # Extrahiere page_info Parameter aus der URL
                page_info_match = re.search(r'page_info=([^&]+)', next_url)
                
                if page_info_match:
                    page_info = page_info_match.group(1)
                    print(f"📄 Nächster page_info cursor gefunden: {page_info[:20]}...")
                    return page_info
                    
        except Exception as e:
            print(f"⚠️ Fehler beim Parsen des Link-Headers: {e}")
            
        return None
    
    def fetch_blog_posts_graphql(self, blog_id: str, limit: int = 250, cursor: Optional[str] = None) -> Tuple[bool, List[Dict], str, Optional[str]]:
        """
        ALTERNATIVE LÖSUNG: Holt Blog-Posts über die moderne GraphQL API
        Dies ist die empfohlene Lösung für neue Entwicklungen ab 2024
        """
        try:
            # GraphQL Query für Blog Articles mit Cursor-Pagination
            query = """
            query getBlogArticles($blogId: ID!, $first: Int!, $after: String) {
              blog(id: $blogId) {
                articles(first: $first, after: $after) {
                  edges {
                    node {
                      id
                      legacyResourceId
                      title
                      handle
                      author {
                        displayName
                      }
                      publishedAt
                      createdAt
                      updatedAt
                      status
                      tags
                      summary
                      content
                      image {
                        url
                        altText
                      }
                    }
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
            """
            
            variables = {
                "blogId": f"gid://shopify/Blog/{blog_id}",
                "first": min(limit, 250)
            }
            
            if cursor:
                variables["after"] = cursor
            
            # GraphQL Request
            response = self._make_request(
                'POST',
                f"{self.base_url.replace('/admin/api/2024-01', '')}/admin/api/2024-10/graphql.json",
                json={
                    'query': query,
                    'variables': variables
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'errors' in data:
                    return False, [], f"GraphQL Errors: {data['errors']}", None
                
                blog_data = data.get('data', {}).get('blog')
                if not blog_data:
                    return False, [], "Blog nicht gefunden", None
                    
                articles_data = blog_data.get('articles', {})
                edges = articles_data.get('edges', [])
                page_info = articles_data.get('pageInfo', {})
                
                # Konvertiere GraphQL Response zu REST-Format für Kompatibilität
                articles = []
                for edge in edges:
                    node = edge['node']
                    article = {
                        'id': int(node['legacyResourceId']),
                        'title': node['title'],
                        'handle': node['handle'],
                        'author': node.get('author', {}).get('displayName', ''),
                        'status': node['status'].lower(),
                        'created_at': node['createdAt'],
                        'updated_at': node['updatedAt'],
                        'published_at': node['publishedAt'],
                        'tags': ','.join(node.get('tags', [])),
                        'body_html': node.get('content', ''),
                        'summary': node.get('summary', ''),
                        'image': {
                            'url': node.get('image', {}).get('url'),
                            'alt': node.get('image', {}).get('altText')
                        } if node.get('image') else None
                    }
                    articles.append(article)
                
                next_cursor = page_info.get('endCursor') if page_info.get('hasNextPage') else None
                
                print(f"✅ GraphQL API: {len(articles)} Blog-Posts abgerufen")
                return True, articles, f"{len(articles)} Blog-Posts via GraphQL abgerufen", next_cursor
                
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}", None
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler bei GraphQL Request: {str(e)}", None
    
    def fetch_single_blog_post(self, blog_id: str, article_id: str) -> Tuple[bool, Optional[Dict], str]:
        """Holt einen einzelnen Blog-Post mit vollständigem Content"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                article = data.get('article')
                return True, article, "Vollständiger Blog-Post abgerufen"
            elif response.status_code == 404:
                return False, None, "Blog-Post nicht gefunden"
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Abrufen des Blog-Posts: {str(e)}"
    
    def fetch_single_collection(self, collection_id: str) -> Tuple[bool, Optional[Dict], str]:
        """Holt eine einzelne Collection von Shopify"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/collections/{collection_id}.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                collection = data.get('collection')
                return True, collection, "Collection erfolgreich abgerufen"
            elif response.status_code == 404:
                return False, None, "Collection nicht gefunden"
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Abrufen der Collection: {str(e)}"
    
    def get_blog_metafields(self, blog_id: str) -> Tuple[bool, List[Dict], str]:
        """Holt Metafields eines Blogs"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/metafields.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                metafields = data.get('metafields', [])
                return True, metafields, f"{len(metafields)} Blog-Metafields gefunden"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Blog-Metafields: {str(e)}"
    
    def get_article_metafields(self, blog_id: str, article_id: str) -> Tuple[bool, List[Dict], str]:
        """Holt Metafields eines Blog-Posts"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}/metafields.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                metafields = data.get('metafields', [])
                return True, metafields, f"{len(metafields)} Artikel-Metafields gefunden"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Artikel-Metafields: {str(e)}"
    
    def get_collection_metafields(self, collection_id: str) -> Tuple[bool, List[Dict], str]:
        """Holt Metafields einer Collection (für SEO Daten)"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/collections/{collection_id}/metafields.json",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                metafields = data.get('metafields', [])
                return True, metafields, f"{len(metafields)} Collection-Metafields gefunden"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Collection-Metafields: {str(e)}"
    
    def update_blog_post(self, blog_id: str, article_id: str, blog_post_data: Dict) -> Tuple[bool, Optional[Dict], str]:
        """Aktualisiert einen Blog-Post in Shopify"""
        try:
            # Bereite Shopify-spezifische Datenstruktur vor
            shopify_data = {
                'article': {
                    'id': int(article_id),
                    'title': blog_post_data.get('title', ''),
                    'body_html': blog_post_data.get('body_html', ''),
                    'summary': blog_post_data.get('summary', ''),
                    'author': blog_post_data.get('author', ''),
                    'tags': blog_post_data.get('tags', ''),
                    'published_at': blog_post_data.get('published_at'),
                }
            }
            
            # SEO-Daten werden separat über Metafields gehandhabt
            # Die Shopify Blog API unterstützt meta_title und meta_description nicht direkt
            
            # Füge Featured Image hinzu falls vorhanden
            if blog_post_data.get('featured_image'):
                featured_image = blog_post_data['featured_image']
                if featured_image.get('url'):
                    shopify_data['article']['image'] = {
                        'url': featured_image['url'],
                        'alt': featured_image.get('alt', '')
                    }
            
            response = self._make_request(
                'PUT',
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}.json",
                json=shopify_data,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                updated_article = data.get('article')
                
                # 2. SEO-Daten über separate Metafields API aktualisieren
                seo_success = True
                seo_messages = []
                
                if blog_post_data.get('seo_title'):
                    success, message = self.update_blog_post_metafield(
                        blog_id, article_id, 'global', 'title_tag', 
                        blog_post_data['seo_title'], 'single_line_text_field'
                    )
                    if success:
                        seo_messages.append("SEO-Titel aktualisiert")
                    else:
                        seo_success = False
                        seo_messages.append(f"SEO-Titel Fehler: {message}")
                
                if blog_post_data.get('seo_description'):
                    success, message = self.update_blog_post_metafield(
                        blog_id, article_id, 'global', 'description_tag', 
                        blog_post_data['seo_description'], 'multi_line_text_field'
                    )
                    if success:
                        seo_messages.append("SEO-Beschreibung aktualisiert")
                    else:
                        seo_success = False
                        seo_messages.append(f"SEO-Beschreibung Fehler: {message}")
                
                # Kombiniere Ergebnisse
                final_message = "Blog-Post erfolgreich aktualisiert"
                if seo_messages:
                    final_message += ". " + "; ".join(seo_messages)
                
                # Rückgabe: True wenn Blog-Post Update erfolgreich war (unabhängig von SEO-Metafields)
                return True, updated_article, final_message
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Blog-Post Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Update des Blog-Posts: {str(e)}"
    
    def update_blog_post_seo_only(self, blog_id: str, article_id: str, seo_title: str = None, seo_description: str = None) -> Tuple[bool, str]:
        """Aktualisiert nur SEO-Metadaten eines Blog-Posts ohne andere Inhalte zu überschreiben"""
        try:
            seo_success = True
            seo_messages = []
            
            # SEO-Titel über Metafields aktualisieren
            if seo_title:
                success, message = self.update_blog_post_metafield(
                    blog_id, article_id, 'global', 'title_tag', 
                    seo_title, 'single_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Titel aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Titel Fehler: {message}")
            
            # SEO-Beschreibung über Metafields aktualisieren
            if seo_description:
                success, message = self.update_blog_post_metafield(
                    blog_id, article_id, 'global', 'description_tag', 
                    seo_description, 'multi_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Beschreibung aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Beschreibung Fehler: {message}")
            
            # Ergebnis zusammenfassen
            if seo_messages:
                final_message = "; ".join(seo_messages)
            else:
                final_message = "Keine SEO-Daten zum Aktualisieren gefunden"
            
            return seo_success, final_message
            
        except Exception as e:
            return False, f"Fehler beim Update der SEO-Metadaten: {str(e)}"

    def update_blog_post_metafield(self, blog_id: str, article_id: str, namespace: str, key: str, value: str, field_type: str) -> Tuple[bool, str]:
        """Aktualisiert oder erstellt ein spezifisches Metafield für einen Blog-Post"""
        try:
            # Erst prüfen, ob das Metafield bereits existiert
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/articles/{article_id}/metafields.json",
                timeout=10
            )
            
            existing_metafield_id = None
            if response.status_code == 200:
                metafields = response.json().get('metafields', [])
                for mf in metafields:
                    if mf.get('namespace') == namespace and mf.get('key') == key:
                        existing_metafield_id = mf.get('id')
                        break
            
            metafield_data = {
                'metafield': {
                    'namespace': namespace,
                    'key': key,
                    'value': value,
                    'type': field_type
                }
            }
            
            if existing_metafield_id:
                # Update existing metafield
                metafield_data['metafield']['id'] = existing_metafield_id
                response = self._make_request(
                    'PUT',
                    f"{self.base_url}/blogs/{blog_id}/articles/{article_id}/metafields/{existing_metafield_id}.json",
                    json=metafield_data,
                    timeout=10
                )
            else:
                # Create new metafield
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/blogs/{blog_id}/articles/{article_id}/metafields.json",
                    json=metafield_data,
                    timeout=10
                )
            
            if response.status_code in [200, 201]:
                return True, f"Metafield {namespace}.{key} erfolgreich {'aktualisiert' if existing_metafield_id else 'erstellt'}"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, f"HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Fehler beim Blog-Post Metafield-Update: {str(e)}"
    
    def update_collection(self, collection_id: str, collection_data: Dict, seo_only: bool = False) -> Tuple[bool, Optional[Dict], str]:
        """Aktualisiert eine Collection in Shopify"""
        try:
            updated_collection = None
            
            # 1. Standard-Collection-Daten aktualisieren (falls nicht nur SEO)
            if not seo_only:
                shopify_data = {
                    'collection': {
                        'id': int(collection_id),
                        'title': collection_data.get('title'),
                        'description': collection_data.get('description'),
                        'published': collection_data.get('published', True),
                        'sort_order': collection_data.get('sort_order', 'best-selling'),
                    }
                }
                
                # Image-Daten falls vorhanden
                if 'image' in collection_data:
                    image_data = collection_data['image']
                    if image_data:
                        shopify_data['collection']['image'] = {
                            'alt': image_data.get('alt', ''),
                            'src': image_data.get('src', '')
                        }
                
                response = self._make_request(
                    'PUT',
                    f"{self.base_url}/collections/{collection_id}.json",
                    json=shopify_data,
                    timeout=15
                )
                
                if response.status_code != 200:
                    try:
                        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    except:
                        error_data = response.text
                    # Für jetzt ignorieren wir Collection-Update Fehler und versuchen nur SEO
                    print(f"⚠️ Collection-Update fehlgeschlagen (HTTP {response.status_code}), versuche nur SEO-Update...")
                else:
                    try:
                        data = response.json()
                        updated_collection = data.get('collection')
                    except:
                        print(f"⚠️ Collection-Update JSON-Parsing fehlgeschlagen, versuche nur SEO-Update...")
            
            # 2. SEO-Daten über separate Metafields API aktualisieren
            seo_success = True
            seo_messages = []
            
            if 'seo_title' in collection_data and collection_data.get('seo_title'):
                success, message = self.update_collection_metafield(
                    collection_id, 'global', 'title_tag', 
                    collection_data['seo_title'], 'single_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Titel aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Titel Fehler: {message}")
            
            if 'seo_description' in collection_data and collection_data.get('seo_description'):
                success, message = self.update_collection_metafield(
                    collection_id, 'global', 'description_tag', 
                    collection_data['seo_description'], 'multi_line_text_field'
                )
                if success:
                    seo_messages.append("SEO-Beschreibung aktualisiert")
                else:
                    seo_success = False
                    seo_messages.append(f"SEO-Beschreibung Fehler: {message}")
            
            # Kombiniere Ergebnisse
            final_message = "Collection erfolgreich aktualisiert"
            if seo_messages:
                final_message += ". " + "; ".join(seo_messages)
            
            return seo_success, updated_collection, final_message
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Collection-Update: {str(e)}"

    def update_collection_metafield(self, collection_id: str, namespace: str, key: str, value: str, field_type: str) -> Tuple[bool, str]:
        """Aktualisiert oder erstellt ein spezifisches Metafield für eine Collection"""
        try:
            # Erst prüfen, ob das Metafield bereits existiert
            success, metafields, message = self.get_collection_metafields(collection_id)
            existing_metafield_id = None
            
            if success:
                for mf in metafields:
                    if isinstance(mf, dict) and mf.get('namespace') == namespace and mf.get('key') == key:
                        existing_metafield_id = mf.get('id')
                        break
            
            metafield_data = {
                'metafield': {
                    'namespace': namespace,
                    'key': key,
                    'value': value,
                    'type': field_type
                }
            }
            
            if existing_metafield_id:
                # Update existing metafield
                metafield_data['metafield']['id'] = existing_metafield_id
                response = self._make_request(
                    'PUT',
                    f"{self.base_url}/collections/{collection_id}/metafields/{existing_metafield_id}.json",
                    json=metafield_data,
                    timeout=10
                )
            else:
                # Create new metafield
                response = self._make_request(
                    'POST',
                    f"{self.base_url}/collections/{collection_id}/metafields.json",
                    json=metafield_data,
                    timeout=10
                )
            
            if response.status_code in [200, 201]:
                return True, f"Metafield {namespace}.{key} erfolgreich {'aktualisiert' if existing_metafield_id else 'erstellt'}"
            else:
                try:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                except:
                    error_data = response.text
                return False, f"HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Fehler beim Collection-Metafield-Update: {str(e)}"
        except Exception as e:
            return False, f"Fehler beim Collection-Metafield-Update: {str(e)}"

    def update_collection_image_alt_text(self, collection_id: str, alt_text: str) -> Tuple[bool, str]:
        """Aktualisiert den Alt-Text eines Collection-Images über GraphQL API"""
        try:
            # GraphQL Mutation für Collection Image Alt-Text Update
            graphql_query = """
            mutation collectionUpdate($input: CollectionInput!) {
              collectionUpdate(input: $input) {
                collection {
                  id
                  title
                  image {
                    altText
                    url
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            variables = {
                "input": {
                    "id": f"gid://shopify/Collection/{collection_id}",
                    "image": {
                        "altText": alt_text
                    }
                }
            }
            
            graphql_data = {
                "query": graphql_query,
                "variables": variables
            }
            
            # GraphQL endpoint
            graphql_url = f"{self.base_url.replace('/admin/api/2023-10', '')}/admin/api/2023-10/graphql.json"
            
            response = self._make_request(
                'POST',
                graphql_url,
                json=graphql_data,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data and 'collectionUpdate' in data['data']:
                    update_data = data['data']['collectionUpdate']
                    
                    # Prüfe auf Fehler
                    if update_data.get('userErrors'):
                        errors = update_data['userErrors']
                        error_messages = [f"{err.get('field', 'unknown')}: {err.get('message', 'unknown error')}" for err in errors]
                        return False, f"GraphQL Fehler: {'; '.join(error_messages)}"
                    
                    # Erfolg prüfen
                    if update_data.get('collection'):
                        collection_data = update_data['collection']
                        image_data = collection_data.get('image', {})
                        updated_alt_text = image_data.get('altText', '')
                        
                        return True, f"Alt-Text erfolgreich aktualisiert: '{updated_alt_text}'"
                    else:
                        return False, "GraphQL Update fehlgeschlagen: Keine Collection-Daten erhalten"
                else:
                    return False, f"GraphQL Antwort-Format unerwartetet: {data}"
            else:
                try:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                except:
                    error_data = response.text
                return False, f"GraphQL HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Fehler beim GraphQL Collection-Image-Update: {str(e)}"


class ShopifyProductSync:
    """Synchronisation zwischen lokaler Datenbank und Shopify"""
    
    def __init__(self, store: ShopifyStore):
        self.store = store
        self.api = ShopifyAPIClient(store)
    
    def _fetch_all_products(self) -> Tuple[bool, List[Dict], str]:
        """Holt alle Produkte über Pagination"""
        all_products = []
        since_id = None
        total_fetched = 0
        
        while True:
            success, products, message = self.api.fetch_products(limit=250, since_id=since_id)
            
            if not success:
                return False, [], message
            
            if not products:  # Keine weiteren Produkte
                break
                
            all_products.extend(products)
            total_fetched += len(products)
            print(f"📦 Produkt Pagination: {len(products)} Produkte geholt, insgesamt: {total_fetched}")
            
            # since_id für nächste Seite setzen
            since_id = str(products[-1]['id'])  # ID des letzten Produkts
            
            # Nur stoppen wenn weniger als 250 Produkte zurückgegeben wurden
            if len(products) < 250:  # Weniger als Maximum = letzte Seite
                break
            
            # Sicherheitscheck: Stoppe bei sehr vielen Produkten
            if total_fetched >= 250000:  # Erhöht für sehr große Shops
                print(f"Sicherheitsstopp bei {total_fetched} Produkten erreicht")
                break
        
        return True, all_products, f"{total_fetched} Produkte über Pagination abgerufen"
    
    def _fetch_next_unimported_products(self, limit: int = 250) -> Tuple[bool, List[Dict], str]:
        """Holt die nächsten nicht-importierten Produkte durch systematisches Durchsuchen"""
        # Da Shopify IDs nicht chronologisch sind, verwenden wir eine andere Strategie:
        # Hole Produkte in Batches und filtere bereits importierte heraus
        
        collected_products = []
        page_limit = 250  # Shopify maximum pro Request
        max_attempts = 10  # Maximale Anzahl von Versuchen
        attempts = 0
        since_id = None
        
        # Erstelle Set mit bereits importierten IDs für schnellere Suche
        existing_ids = set(
            ShopifyProduct.objects.filter(store=self.store)
            .values_list('shopify_id', flat=True)
        )
        
        print(f"Bereits importierte Produkte: {len(existing_ids)}")
        
        while len(collected_products) < limit and attempts < max_attempts:
            attempts += 1
            
            # Hole nächsten Batch von Shopify
            success, products, message = self.api.fetch_products(
                limit=page_limit, 
                since_id=since_id
            )
            
            if not success:
                return False, [], message
            
            if not products:  # Keine weiteren Produkte verfügbar
                print(f"Keine weiteren Produkte bei Versuch {attempts}")
                break
            
            print(f"Versuch {attempts}: {len(products)} Produkte von Shopify geholt")
            
            # Filtere nicht-importierte Produkte
            new_products_in_batch = 0
            for product in products:
                shopify_id = str(product.get('id'))
                if shopify_id not in existing_ids:
                    collected_products.append(product)
                    new_products_in_batch += 1
                    if len(collected_products) >= limit:
                        break
            
            print(f"  → {new_products_in_batch} neue Produkte gefunden")
            
            # Update since_id für nächste Iteration
            since_id = str(products[-1]['id'])
            
            # Wenn wir genug haben, stoppe
            if len(collected_products) >= limit:
                break
                
            # Wenn keine neuen Produkte in diesem Batch, versuche noch ein paar Mal
            if new_products_in_batch == 0:
                print(f"  → Kein neues Produkt in diesem Batch, weitersuchen...")
        
        result_count = len(collected_products)
        message = f"{result_count} nicht-importierte Produkte gefunden nach {attempts} Versuchen"
        
        return True, collected_products[:limit], message
    
    def import_products(self, limit: int = 250, import_mode: str = 'all', 
                       overwrite_existing: bool = True, import_images: bool = True) -> ShopifySyncLog:
        """Importiert Produkte von Shopify"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import',
            status='success'
        )
        
        try:
            # Bei "reset_and_import" - alle lokalen Produkte löschen
            if overwrite_existing:
                deleted_count = self._delete_all_local_products()
                print(f"🗑️ {deleted_count} lokale Produkte gelöscht vor Neuimport")
            
            # Hole Produkte je nach Modus
            if import_mode == 'new_only':
                # Finde nur die nächsten nicht-importierten Produkte
                success, products, message = self._fetch_next_unimported_products(limit=limit)
            else:
                # Standard: Hole einfach die nächsten 250 Produkte (für reset_and_import)
                success, products, message = self.api.fetch_products(limit=limit)
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = django_timezone.now()
                log.save()
                return log
            
            log.products_processed = len(products)
            success_count = 0
            failed_count = 0
            
            # SQLite-optimierte Verarbeitung in kleineren Batches
            from django.db import transaction
            batch_size = 25  # Kleinere Batches für SQLite
            
            for i, product_data in enumerate(products):
                try:
                    shopify_id = str(product_data.get('id'))
                    
                    # Prüfe ob Produkt bereits existiert (für new_only Modus)
                    existing_product = None
                    if import_mode == 'new_only':
                        try:
                            existing_product = ShopifyProduct.objects.get(
                                shopify_id=shopify_id, 
                                store=self.store
                            )
                            # Produkt existiert bereits - überspringen
                            print(f"Produkt {shopify_id} bereits vorhanden - überspringe (new_only Modus)")
                            continue
                        except ShopifyProduct.DoesNotExist:
                            # Produkt existiert noch nicht - kann importiert werden
                            pass
                    
                    # Debug: Erste paar Produkte ausgeben um Struktur zu verstehen
                    if success_count < 2:
                        print(f"Debug - Shopify Produktdaten für ID {shopify_id}:")
                        print(f"  Verfügbare Keys: {list(product_data.keys())}")
                        if 'seo' in product_data:
                            print(f"  SEO Daten: {product_data['seo']}")
                        if 'meta_title' in product_data:
                            print(f"  Meta Title: {product_data['meta_title']}")
                        if 'meta_description' in product_data:
                            print(f"  Meta Description: {product_data['meta_description']}")
                    
                    # Produkt erstellen oder aktualisieren mit Retry-Logik für SQLite
                    if import_mode == 'all' or existing_product is None:
                        product, created = self._create_or_update_product_with_retry(
                            product_data, 
                            overwrite_existing=overwrite_existing,
                            import_images=import_images
                        )
                        success_count += 1
                        if created:
                            print(f"Produkt {shopify_id} erstellt: {product.title}")
                            if success_count < 3:
                                print(f"  SEO Titel: '{product.seo_title}'")
                                print(f"  SEO Beschreibung: '{product.seo_description}'")
                        else:
                            print(f"Produkt {shopify_id} aktualisiert: {product.title}")
                    
                    # Periodische Commits für SQLite-Performance
                    if (i + 1) % batch_size == 0:
                        try:
                            transaction.commit()
                            print(f"Batch-Commit nach {i + 1} Produkten")
                        except Exception as commit_error:
                            print(f"Batch-Commit Fehler: {commit_error}")
                            
                except Exception as e:
                    failed_count += 1
                    import traceback
                    error_details = traceback.format_exc()
                    product_title = product_data.get('title', 'Unknown')
                    product_id = product_data.get('id', 'Unknown')
                    
                    print(f"❌ Fehler beim Importieren von Produkt '{product_title}' (ID: {product_id}): {e}")
                    print(f"Vollständiger Fehler: {error_details}")
                    
                    # Sammle detaillierte Fehlerinformationen
                    error_info = {
                        'product_id': product_id,
                        'product_title': product_title,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'error_details': error_details[:500]  # Begrenzen für bessere Lesbarkeit
                    }
                    
                    # Speichere den Fehler im Log für spätere Analyse
                    if not hasattr(log, '_errors'):
                        log._errors = []
                        
                    # Häufigste Fehlertypen kategorisieren
                    common_errors = {
                        'IntegrityError': 'Datenbankintegritätsfehler (z.B. doppelte Einträge)',
                        'DataError': 'Datenformat-Fehler (z.B. zu lange Strings)',
                        'ValidationError': 'Django-Validierungsfehler',
                        'KeyError': 'Fehlende erforderliche Shopify-Datenfelder',
                        'ValueError': 'Ungültige Datenkonvertierung (z.B. Preise)',
                        'DecimalInvalidOperation': 'Ungültige Dezimalzahl-Operation'
                    }
                    
                    error_category = common_errors.get(type(e).__name__, 'Unbekannter Fehler')
                    error_info['category'] = error_category
                    log._errors.append(error_info)
            
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = django_timezone.now()
            
            # Speichere Fehlerdetails im details-Feld
            if hasattr(log, '_errors') and log._errors:
                import json
                # Kategorisiere Fehler für besseren Überblick
                error_summary = {}
                for error in log._errors:
                    error_type = error['error_type']
                    if error_type not in error_summary:
                        error_summary[error_type] = {'count': 0, 'examples': []}
                    error_summary[error_type]['count'] += 1
                    if len(error_summary[error_type]['examples']) < 3:  # Nur erste 3 Beispiele
                        error_summary[error_type]['examples'].append({
                            'product_id': error['product_id'],
                            'product_title': error['product_title'][:50],
                            'error_message': error['error_message'][:100]
                        })
                
                log.details = json.dumps({
                    'error_summary': error_summary,
                    'total_errors': len(log._errors)
                }, ensure_ascii=False)
            
            log.save()
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = django_timezone.now()
            log.save()
        
        return log
    
    def _delete_all_local_products(self):
        """Löscht alle lokalen Produkte für diesen Store"""
        from .models import ShopifyProduct
        deleted_count, _ = ShopifyProduct.objects.filter(store=self.store).delete()
        return deleted_count
    
    def sync_product_to_shopify(self, product: ShopifyProduct) -> Tuple[bool, str]:
        """Synchronisiert ein lokales Produkt zurück zu Shopify"""
        try:
            product_data = {
                'title': product.title,
                'body_html': product.body_html,
                'vendor': product.vendor,
                'product_type': product.product_type,
                'status': product.status,
                'tags': product.tags,
                'seo_title': product.seo_title,
                'seo_description': product.seo_description,
            }
            
            # Füge Bilder hinzu wenn sie in raw_shopify_data vorhanden sind
            if product.raw_shopify_data and 'images' in product.raw_shopify_data:
                images = product.raw_shopify_data['images']
                if images:  # Nur wenn Bilder vorhanden sind
                    print(f"DEBUG: Synchronisiere {len(images)} Bilder für Produkt {product.shopify_id}")
                    
                    # Erst die Standard-Produktdaten aktualisieren
                    success, updated_product, message = self.api.update_product(
                        product.shopify_id, 
                        product_data
                    )
                    
                    if not success:
                        return False, message
                    
                    # Dann die Bilder separat aktualisieren
                    images_success, images_updated_product, images_message = self.api.update_product_images(
                        product.shopify_id,
                        images
                    )
                    
                    if images_success:
                        message += f"; Bilder aktualisiert: {images_message}"
                    else:
                        # Fallback: Versuche einzelne Bilder zu aktualisieren
                        print(f"DEBUG: Bulk-Bild-Update fehlgeschlagen, versuche einzelne Updates...")
                        individual_success_count = 0
                        individual_error_count = 0
                        
                        for img in images:
                            if 'id' in img and 'alt' in img:
                                single_success, single_message = self.api.update_single_product_image(
                                    product.shopify_id,
                                    str(img['id']),
                                    str(img['alt'])
                                )
                                if single_success:
                                    individual_success_count += 1
                                else:
                                    individual_error_count += 1
                                    print(f"DEBUG: Einzelbild-Update fehlgeschlagen für Bild {img['id']}: {single_message}")
                        
                        if individual_success_count > 0:
                            message += f"; {individual_success_count} Bilder einzeln aktualisiert"
                            if individual_error_count > 0:
                                message += f" ({individual_error_count} Fehler)"
                        else:
                            message += f"; Bilder-Fehler: {images_message}"
                else:
                    success, updated_product, message = self.api.update_product(
                        product.shopify_id, 
                        product_data
                    )
            else:
                success, updated_product, message = self.api.update_product(
                    product.shopify_id, 
                    product_data
                )
            
            if success:
                # Update lokales Produkt mit Shopify Daten
                product.last_synced_at = django_timezone.now()
                product.needs_sync = False
                product.sync_error = ""
                
                if updated_product:
                    product.shopify_updated_at = self._parse_shopify_datetime(
                        updated_product.get('updated_at')
                    )
                
                product.save()
                return True, "Erfolgreich synchronisiert"
            else:
                product.sync_error = message
                product.save()
                return False, message
                
        except Exception as e:
            error_msg = f"Sync-Fehler: {str(e)}"
            product.sync_error = error_msg
            product.save()
            return False, error_msg
    
    def _create_or_update_product(self, product_data: Dict, overwrite_existing: bool = True, import_images: bool = True) -> Tuple[ShopifyProduct, bool]:
        """Erstellt oder aktualisiert ein lokales Produkt basierend auf Shopify Daten"""
        shopify_id = str(product_data['id'])
        
        # Extrahiere Hauptbild
        featured_image_url = ""
        featured_image_alt = ""
        images = product_data.get('images', [])
        if images:
            featured_image = images[0]
            featured_image_url = featured_image.get('src', '')
            featured_image_alt = featured_image.get('alt', '')
        
        # Extrahiere Preis aus Varianten - Robustere Preis-Extraktion
        price = None
        compare_at_price = None
        variants = product_data.get('variants', [])
        if variants:
            first_variant = variants[0] if isinstance(variants, list) else {}
            
            # Sichere Preis-Extraktion
            def safe_decimal(value):
                if value is None or value == '':
                    return None
                try:
                    from decimal import Decimal, InvalidOperation
                    # Entferne mögliche Leerzeichen und konvertiere zu String
                    clean_value = str(value).strip()
                    if clean_value == '' or clean_value.lower() == 'null':
                        return None
                    return Decimal(clean_value)
                except (ValueError, TypeError, InvalidOperation):
                    return None
            
            price = safe_decimal(first_variant.get('price'))
            compare_at_price = safe_decimal(first_variant.get('compare_at_price'))
        
        # Hole SEO Daten aus Shopify Produktdaten
        seo_title = ""
        seo_description = ""
        
        # Shopify speichert SEO-Daten im Hauptprodukt
        if 'seo' in product_data:
            seo_data = product_data['seo']
            seo_title = seo_data.get('title', '')
            seo_description = seo_data.get('description', '')
        
        # Fallback: manchmal sind die SEO-Daten direkt im Produkt
        if not seo_title and 'meta_title' in product_data:
            seo_title = product_data.get('meta_title', '')
        if not seo_description and 'meta_description' in product_data:
            seo_description = product_data.get('meta_description', '')
            
        # Weitere Fallback: Titel als SEO-Titel verwenden falls leer
        if not seo_title:
            seo_title = product_data.get('title', '')[:70]
        
        # Prüfe ob Produkt bereits existiert (für overwrite_existing Check)
        existing_product = None
        try:
            existing_product = ShopifyProduct.objects.get(shopify_id=shopify_id, store=self.store)
        except ShopifyProduct.DoesNotExist:
            pass
        
        # Wenn Produkt existiert und overwrite_existing=False, dann überspringen
        if existing_product and not overwrite_existing:
            print(f"Produkt {shopify_id} existiert bereits und overwrite_existing=False - überspringe")
            return existing_product, False
        
        # Erstelle oder aktualisiere Produkt
        try:
            # Sichere Datenextraktion mit Fallbacks
            def safe_string(value, max_length=255, default=''):
                if value is None:
                    return default
                return str(value)[:max_length] if value else default
            
            def safe_text(value, default=''):
                if value is None:
                    return default
                return str(value) if value else default
            
            defaults = {
                'title': safe_string(product_data.get('title'), 255, 'Unbekanntes Produkt'),
                'handle': safe_string(product_data.get('handle'), 255),
                'body_html': safe_text(product_data.get('body_html')),
                'vendor': safe_string(product_data.get('vendor'), 255),
                'product_type': safe_string(product_data.get('product_type'), 255),
                'status': safe_string(product_data.get('status'), 50, 'active'),
                'seo_title': safe_string(seo_title, 70),
                'seo_description': safe_string(seo_description, 160),
                'featured_image_url': safe_string(featured_image_url, 500),
                'featured_image_alt': safe_string(featured_image_alt, 255),
                'price': price,
                'compare_at_price': compare_at_price,
                'tags': safe_text(product_data.get('tags')),
                'shopify_created_at': self._parse_shopify_datetime(product_data.get('created_at')),
                'shopify_updated_at': self._parse_shopify_datetime(product_data.get('updated_at')),
                'last_synced_at': django_timezone.now(),
                'needs_sync': False,
                'raw_shopify_data': product_data if isinstance(product_data, dict) else {},
            }
            
            product, created = ShopifyProduct.objects.update_or_create(
                shopify_id=shopify_id,
                store=self.store,
                defaults=defaults
            )
        except Exception as e:
            print(f"Fehler bei update_or_create für Produkt {shopify_id}: {e}")
            print(f"Produktdaten: {product_data}")
            raise
        
        # Erstelle Produktbilder (nur wenn import_images=True)
        if created and images and import_images:
            self._create_product_images(product, images)
        
        # Hole SEO-Daten über Metafields für ALLE Produkte (nicht nur neue)
        try:
            self._fetch_and_update_seo_data(product)
        except Exception as e:
            print(f"Warnung: Konnte SEO-Daten für Produkt {product.shopify_id} nicht abrufen: {e}")
        
        return product, created
    
    def _create_or_update_product_with_retry(self, product_data: Dict, overwrite_existing: bool = True, import_images: bool = True, max_retries: int = 3) -> Tuple[ShopifyProduct, bool]:
        """Erstellt oder aktualisiert ein Produkt mit Retry-Logik für SQLite-Sperren"""
        import time
        from django.db import OperationalError
        
        for attempt in range(max_retries):
            try:
                return self._create_or_update_product(product_data, overwrite_existing, import_images)
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s, 0.4s
                    wait_time = 0.1 * (2 ** attempt)
                    print(f"Database locked, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Letzter Versuch oder anderer Fehler
                    raise
            except Exception as e:
                # Andere Fehler sofort weiterwerfen
                raise
        
        # Sollte nie erreicht werden
        raise Exception("Retry-Logik fehlgeschlagen")
    
    def _create_product_images(self, product: ShopifyProduct, images: List[Dict]):
        """Erstellt Produktbilder für ein Produkt"""
        # Lösche bestehende Bilder
        product.images.all().delete()
        
        for i, image_data in enumerate(images):
            # Sichere alt_text Behandlung
            alt_text = image_data.get('alt', '') or None  # Leeren String zu None konvertieren
            
            ShopifyProductImage.objects.create(
                product=product,
                shopify_image_id=str(image_data.get('id', '')),
                image_url=image_data.get('src', ''),
                alt_text=alt_text,
                position=i + 1
            )
    
    def _fetch_and_update_seo_data(self, product: ShopifyProduct):
        """Holt SEO-Daten über Metafields API"""
        try:
            success, metafields, message = self.api.get_product_metafields(product.shopify_id)
            
            print(f"Metafields-Abruf für Produkt {product.shopify_id}: {success}")
            print(f"Metafields Typ: {type(metafields)}")
            print(f"Metafields Inhalt: {metafields}")
            print(f"Message: {message}")
            
        except Exception as e:
            print(f"Fehler beim Metafields-Abruf: {e}")
            return
        
        if success and metafields and isinstance(metafields, list):
            seo_title = ""
            seo_description = ""
            
            print(f"Verfügbare Metafields: {[(m.get('namespace', ''), m.get('key', ''), str(m.get('value', ''))[:50]) for m in metafields if isinstance(m, dict)]}")
            
            for metafield in metafields:
                if not isinstance(metafield, dict):
                    print(f"Warnung: Metafield ist kein Dict: {type(metafield)} = {metafield}")
                    continue
                    
                namespace = metafield.get('namespace', '')
                key = metafield.get('key', '')
                value = str(metafield.get('value', ''))
                
                print(f"Prüfe Metafield: {namespace}.{key} = '{value[:50]}...'")
                
                # SEO Metafield Patterns - GLOBAL NAMESPACE hat höchste Priorität (Webrex verwendet diesen!)
                title_patterns = [
                    # HÖCHSTE PRIORITÄT: Global Namespace (von Webrex SEO AI Optimizer verwendet)
                    (namespace == 'global' and key == 'title_tag'),
                    # Standard SEO Fields 
                    (namespace == 'seo' and key == 'title'),
                    (namespace == 'seo' and key == 'meta_title'),
                    (namespace == 'custom' and key == 'meta_title'),
                    (key == 'meta_title'),
                    (key == 'seo_title'),
                    (key == 'title_tag'),
                    # Shopify Standard SEO
                    (namespace == 'descriptors' and key == 'title'),
                    (namespace == 'shopify' and key == 'seo_title'),
                    # Fallback: Webrex-spezifische Patterns (falls sie doch verwendet werden)
                    (namespace == 'webrex' and key == 'title'),
                    (namespace == 'webrex' and key == 'meta_title'),
                    (namespace == 'webrex' and key == 'seo_title'),
                    (namespace == 'webrex_seo' and key == 'title'),
                    (namespace == 'webrex_seo' and key == 'meta_title'),
                    ('webrex' in namespace and 'title' in key),
                    ('webrex' in namespace and 'meta_title' in key),
                ]
                
                description_patterns = [
                    # HÖCHSTE PRIORITÄT: Global Namespace (von Webrex SEO AI Optimizer verwendet)
                    (namespace == 'global' and key == 'description_tag'),
                    # Standard SEO Fields
                    (namespace == 'seo' and key == 'description'),
                    (namespace == 'seo' and key == 'meta_description'),
                    (namespace == 'custom' and key == 'meta_description'),
                    (key == 'meta_description'),
                    (key == 'seo_description'),
                    (key == 'description_tag'),
                    # Shopify Standard SEO
                    (namespace == 'descriptors' and key == 'description'),
                    (namespace == 'shopify' and key == 'seo_description'),
                    # Fallback: Webrex-spezifische Patterns (falls sie doch verwendet werden)
                    (namespace == 'webrex' and key == 'description'),
                    (namespace == 'webrex' and key == 'meta_description'),
                    (namespace == 'webrex' and key == 'seo_description'),
                    (namespace == 'webrex_seo' and key == 'description'),
                    (namespace == 'webrex_seo' and key == 'meta_description'),
                    ('webrex' in namespace and 'description' in key),
                    ('webrex' in namespace and 'meta_description' in key),
                ]
                
                # Prüfe Title Patterns
                title_match = any(title_patterns)
                if title_match and value and not seo_title:
                    seo_title = value
                    print(f"✅ SEO-Titel gefunden: {namespace}.{key} = '{value[:50]}...'")
                elif title_match:
                    print(f"🔍 Title Pattern Match aber übersprungen: {namespace}.{key}, value='{value[:30]}...', bereits seo_title='{seo_title[:30] if seo_title else 'None'}...'")
                    
                # Prüfe Description Patterns
                description_match = any(description_patterns)
                if description_match and value and not seo_description:
                    seo_description = value
                    print(f"✅ SEO-Beschreibung gefunden: {namespace}.{key} = '{value[:50]}...'")
                elif description_match:
                    print(f"🔍 Description Pattern Match aber übersprungen: {namespace}.{key}, value='{value[:30]}...', bereits seo_description='{seo_description[:30] if seo_description else 'None'}...'")
                else:
                    print(f"❌ Kein Pattern Match für: {namespace}.{key}")
                
                # Fallback: Allgemeine SEO-Erkennung für unbekannte App-Strukturen
                if not seo_title and value:
                    key_lower = key.lower()
                    namespace_lower = namespace.lower()
                    # Suche nach Variationen von "title" in Kombination mit SEO-Keywords
                    if any(word in key_lower for word in ['title', 'headline']) and \
                       any(word in (key_lower + namespace_lower) for word in ['seo', 'meta', 'tag', 'webrex', 'optimizer']):
                        seo_title = value
                        print(f"✅ SEO-Titel (Fallback) gefunden: {namespace}.{key}")
                
                if not seo_description and value:
                    key_lower = key.lower()
                    namespace_lower = namespace.lower()
                    # Suche nach Variationen von "description" in Kombination mit SEO-Keywords
                    if any(word in key_lower for word in ['description', 'desc', 'summary']) and \
                       any(word in (key_lower + namespace_lower) for word in ['seo', 'meta', 'tag', 'webrex', 'optimizer']):
                        seo_description = value
                        print(f"✅ SEO-Beschreibung (Fallback) gefunden: {namespace}.{key}")
            
            # Update das Produkt wenn SEO-Daten gefunden wurden
            updated = False
            if seo_title and seo_title != product.seo_title:
                product.seo_title = seo_title[:70]
                updated = True
                print(f"SEO-Titel aktualisiert: '{seo_title[:50]}...'")
                
            if seo_description and seo_description != product.seo_description:
                product.seo_description = seo_description[:160]
                updated = True
                print(f"SEO-Beschreibung aktualisiert: '{seo_description[:50]}...'")
            
            if updated:
                product.save(update_fields=['seo_title', 'seo_description'])
                print(f"SEO-Daten für Produkt {product.shopify_id} gespeichert")
            else:
                print(f"Keine neuen SEO-Daten für Produkt {product.shopify_id}")
        else:
            print(f"Keine Metafields gefunden für Produkt {product.shopify_id}: {message}")
    
    def _parse_shopify_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Konvertiert Shopify DateTime String zu Python datetime"""
        if not datetime_str:
            return None
        
        try:
            # Shopify verwendet ISO 8601 Format
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None


class ShopifyBlogSync:
    """Synchronisation für Blogs und Blog-Posts"""
    
    def __init__(self, store: ShopifyStore):
        self.store = store
        self.api = ShopifyAPIClient(store)
    
    def import_blogs(self) -> ShopifySyncLog:
        """Importiert Blogs von Shopify"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_blogs',
            status='success'
        )
        
        try:
            success, blogs, message = self.api.fetch_blogs()
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = django_timezone.now()
                log.save()
                return log
            
            log.products_processed = len(blogs)
            success_count = 0
            failed_count = 0
            
            for blog_data in blogs:
                try:
                    blog, created = self._create_or_update_blog(blog_data)
                    success_count += 1
                    if created:
                        print(f"Blog {blog.shopify_id} erstellt: {blog.title}")
                    else:
                        print(f"Blog {blog.shopify_id} aktualisiert: {blog.title}")
                        
                except Exception as e:
                    failed_count += 1
                    print(f"Fehler beim Importieren von Blog {blog_data.get('title', 'Unknown')}: {e}")
            
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = django_timezone.now()
            log.save()
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = django_timezone.now()
            log.save()
        
        return log

    def _fetch_all_blog_posts(self, blog_id: str) -> Tuple[bool, List[Dict], str]:
        """Holt alle Blog-Posts über moderne cursor-basierte Pagination"""
        all_articles = []
        page_info = None
        total_fetched = 0
        page_count = 0

        print(f"🚀 Starte vollständigen Blog-Post Import mit cursor-basierter Pagination...")

        while True:
            page_count += 1
            print(f"📄 Lade Seite {page_count}...")
            
            # Hier wird die API-Client-Methode mit modernen Parametern aufgerufen
            success, articles, message, next_page_info = self.api.fetch_blog_posts(blog_id, limit=250, page_info=page_info)

            if not success:
                return False, [], message

            if not articles:  # Keine weiteren Artikel
                print(f"📄 Keine weiteren Blog-Posts gefunden - Import beendet")
                break

            all_articles.extend(articles)
            total_fetched += len(articles)
            print(f"📄 Seite {page_count}: {len(articles)} Blog-Posts geholt, insgesamt: {total_fetched}")

            # Prüfe ob es eine nächste Seite gibt
            if not next_page_info:
                print(f"📄 Letzte Seite erreicht - keine weitere page_info im Link-Header")
                break
                
            # Setze page_info für nächste Seite
            page_info = next_page_info

            # Sicherheitscheck: Stoppe bei sehr vielen Artikeln
            if total_fetched >= 250000:  # Sicherheitslimit
                print(f"⚠️ Sicherheitsstopp bei {total_fetched} Blog-Posts erreicht")
                break
                
            # Sicherheitscheck: Zu viele Seiten
            if page_count >= 1000:  # 1000 Seiten * 250 = 250.000 Posts max
                print(f"⚠️ Sicherheitsstopp bei {page_count} Seiten erreicht")
                break

        print(f"✅ Blog-Post Import abgeschlossen: {total_fetched} Posts in {page_count} Seiten")
        return True, all_articles, f"{total_fetched} Blog-Posts über cursor-basierte Pagination abgerufen"
    
    def _fetch_all_blog_posts_graphql(self, blog_id: str) -> Tuple[bool, List[Dict], str]:
        """
        ALTERNATIVE LÖSUNG: Holt alle Blog-Posts über GraphQL API
        Dies ist die zukunftssichere Lösung und sollte bei Problemen mit REST API verwendet werden
        """
        all_articles = []
        cursor = None
        total_fetched = 0
        page_count = 0

        print(f"🚀 Starte vollständigen Blog-Post Import mit GraphQL API...")

        while True:
            page_count += 1
            print(f"📄 Lade Seite {page_count} (GraphQL)...")
            
            # Verwende die GraphQL-Methode
            success, articles, message, next_cursor = self.api.fetch_blog_posts_graphql(blog_id, limit=250, cursor=cursor)

            if not success:
                return False, [], message

            if not articles:  # Keine weiteren Artikel
                print(f"📄 Keine weiteren Blog-Posts gefunden - GraphQL Import beendet")
                break

            all_articles.extend(articles)
            total_fetched += len(articles)
            print(f"📄 Seite {page_count}: {len(articles)} Blog-Posts geholt, insgesamt: {total_fetched}")

            # Prüfe ob es eine nächste Seite gibt
            if not next_cursor:
                print(f"📄 Letzte Seite erreicht - kein weiterer cursor")
                break
                
            # Setze cursor für nächste Seite
            cursor = next_cursor

            # Sicherheitscheck: Stoppe bei sehr vielen Artikeln
            if total_fetched >= 250000:  # Sicherheitslimit
                print(f"⚠️ Sicherheitsstopp bei {total_fetched} Blog-Posts erreicht")
                break
                
            # Sicherheitscheck: Zu viele Seiten
            if page_count >= 1000:  # 1000 Seiten * 250 = 250.000 Posts max
                print(f"⚠️ Sicherheitsstopp bei {page_count} Seiten erreicht")
                break

        print(f"✅ GraphQL Blog-Post Import abgeschlossen: {total_fetched} Posts in {page_count} Seiten")
        return True, all_articles, f"{total_fetched} Blog-Posts über GraphQL API abgerufen"
    
    def _fetch_all_blog_posts_with_fallback(self, blog_id: str) -> Tuple[bool, List[Dict], str]:
        """
        ROBUSTE LÖSUNG: Versucht verschiedene Methoden um alle Blog-Posts zu laden
        1. Moderne REST API mit Link-Headers
        2. GraphQL API als Fallback
        3. Alter Ansatz als letzter Fallback (falls nötig)
        """
        print(f"🔄 Starte robusten Blog-Post Import mit Fallback-Strategien...")
        
        # VERSUCH 1: Moderne REST API mit Link-Headers
        try:
            print(f"🔄 Versuche moderne REST API mit cursor-basierter Pagination...")
            success, articles, message = self._fetch_all_blog_posts(blog_id)
            
            if success and articles:
                print(f"✅ Moderne REST API erfolgreich: {len(articles)} Blog-Posts")
                return True, articles, f"{len(articles)} Blog-Posts via moderne REST API geladen"
            else:
                print(f"⚠️ Moderne REST API fehlgeschlagen: {message}")
                
        except Exception as e:
            print(f"⚠️ Moderne REST API Fehler: {e}")
        
        # VERSUCH 2: GraphQL API als Fallback
        try:
            print(f"🔄 Fallback zu GraphQL API...")
            success, articles, message = self._fetch_all_blog_posts_graphql(blog_id)
            
            if success and articles:
                print(f"✅ GraphQL API erfolgreich: {len(articles)} Blog-Posts")
                return True, articles, f"{len(articles)} Blog-Posts via GraphQL API geladen"
            else:
                print(f"⚠️ GraphQL API fehlgeschlagen: {message}")
                
        except Exception as e:
            print(f"⚠️ GraphQL API Fehler: {e}")
        
        # VERSUCH 3: Notfall-Fallback (einzelne Requests)
        try:
            print(f"🔄 Letzter Fallback: Versuche einzelne API-Calls...")
            
            # Hole erste 250 Posts
            success, articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=250)
            
            if success and articles:
                print(f"⚠️ Nur erste 250 Blog-Posts geladen - manueller Import erforderlich")
                return True, articles, f"WARNUNG: Nur {len(articles)} von möglicherweise mehr Blog-Posts geladen"
            else:
                print(f"❌ Auch Notfall-Fallback fehlgeschlagen: {message}")
                
        except Exception as e:
            print(f"❌ Notfall-Fallback Fehler: {e}")
        
        return False, [], "ALLE Import-Methoden fehlgeschlagen - API-Problem oder Konfigurationsfehler"

    def _fetch_next_unimported_blog_posts(self, blog: ShopifyBlog, limit: int = 250) -> Tuple[bool, List[Dict], str]:
        """Holt die nächsten nicht-importierten Blog-Posts durch cursor-basierte Pagination"""
        try:
            # Hole bereits importierte Blog-Post-IDs für diesen Blog
            existing_ids = set(
                ShopifyBlogPost.objects.filter(blog=blog)
                .values_list('shopify_id', flat=True)
            )
            print(f"📊 {len(existing_ids)} Blog-Posts bereits in lokaler DB für Blog {blog.title}")
            
            # Iteriere durch Shopify-Blog-Posts und finde unimportierte
            all_articles = []
            page_info = None
            found_unimported = 0
            page_count = 0
            
            while found_unimported < limit:
                page_count += 1
                
                # Hole nächste Batch von Shopify mit cursor-basierter Pagination
                success, articles, message, next_page_info = self.api.fetch_blog_posts(blog.shopify_id, limit=250, page_info=page_info)
                
                if not success:
                    return False, [], message
                
                if not articles:  # Keine weiteren Blog-Posts
                    print(f"📄 Keine weiteren Blog-Posts bei Suche nach unimportierten Posts")
                    break
                
                print(f"📄 Prüfe {len(articles)} Blog-Posts auf Import-Status (Seite {page_count})...")
                
                # Filtere unimportierte Blog-Posts
                unimported_articles = []
                for article in articles:
                    if str(article['id']) not in existing_ids:
                        unimported_articles.append(article)
                        found_unimported += 1
                        
                        if found_unimported >= limit:
                            break
                
                all_articles.extend(unimported_articles)
                print(f"🆕 {len(unimported_articles)} neue Blog-Posts gefunden, insgesamt: {found_unimported}")
                
                # Prüfe ob es eine nächste Seite gibt
                if not next_page_info:
                    print(f"📄 Letzte Seite erreicht bei Blog-Post-Suche")
                    break
                    
                # Setze page_info für nächste Seite
                page_info = next_page_info
                
                # Sicherheitscheck gegen endlose Schleifen
                if page_count >= 100:  # Max 100 Seiten durchsuchen
                    print(f"⚠️ Sicherheitsstopp nach {page_count} durchsuchten Seiten")
                    break
            
            return True, all_articles[:limit], f"{len(all_articles[:limit])} neue Blog-Posts gefunden"
            
        except Exception as e:
            print(f"❌ Fehler beim Suchen neuer Blog-Posts: {e}")
            return False, [], f"Fehler beim Suchen: {str(e)}"

    def import_blog_posts(self, blog: ShopifyBlog, import_mode: str = 'new_only') -> ShopifySyncLog:
        """Importiert Blog-Posts für einen bestimmten Blog"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_blog_posts',
            status='success'
        )
        
        try:
            # Import-Modus behandeln
            if import_mode == 'reset_and_import':
                # Alle lokalen Blog-Posts für diesen Blog löschen und erste 250 importieren
                deleted_count = self._delete_all_local_blog_posts(blog)
                print(f"🗑️ {deleted_count} lokale Blog-Posts gelöscht vor Neuimport für Blog {blog.title}")
                success, articles, message, _ = self.api.fetch_blog_posts(blog.shopify_id, limit=250)
            elif import_mode == 'new_only':
                # Nächste 250 neue Blog-Posts importieren
                success, articles, message = self._fetch_next_unimported_blog_posts(blog, limit=250)
            elif import_mode == 'all_robust':
                # NEUE OPTION: Alle Blog-Posts mit robusten Fallback-Strategien
                success, articles, message = self._fetch_all_blog_posts_with_fallback(blog.shopify_id)
            elif import_mode == 'all_graphql':
                # NEUE OPTION: Alle Blog-Posts nur über GraphQL
                success, articles, message = self._fetch_all_blog_posts_graphql(blog.shopify_id)
            else:
                # Fallback: alle Blog-Posts mit moderner cursor-basierter Pagination
                success, articles, message = self._fetch_all_blog_posts(blog.shopify_id)
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = django_timezone.now()
                log.save()
                return log
            
            log.products_processed = len(articles)
            success_count = 0
            failed_count = 0
            
            print(f"🚀 Starte Verarbeitung von {len(articles)} Blog-Posts...")
            print(f"🔄 Import-Modus: {import_mode}")
            
            for i, article_data in enumerate(articles):
                try:
                    shopify_id = str(article_data.get('id'))
                    
                    # Bei "new_only" prüfen ob Post bereits existiert
                    if import_mode == 'new_only':
                        try:
                            from .models import ShopifyBlogPost
                            existing_post = ShopifyBlogPost.objects.get(
                                shopify_id=shopify_id,
                                blog=blog
                            )
                            # Post existiert bereits - überspringen
                            print(f"Blog-Post {shopify_id} bereits vorhanden - überspringe (new_only Modus)")
                            continue
                        except ShopifyBlogPost.DoesNotExist:
                            # Post existiert noch nicht - kann importiert werden
                            pass
                    
                    post, created = self._create_or_update_blog_post(blog, article_data)
                    success_count += 1
                    
                    # Debug: Verfolge jeden 50. Post
                    if (i + 1) % 50 == 0:
                        print(f"📊 Verarbeitet: {i + 1}/{len(articles)} Posts (Success: {success_count}, Failed: {failed_count})")
                    
                    if created:
                        print(f"✅ Blog-Post {post.shopify_id} erstellt: {post.title[:50]}...")
                    else:
                        print(f"🔄 Blog-Post {post.shopify_id} aktualisiert: {post.title[:50]}...")
                        
                except Exception as e:
                    failed_count += 1
                    import traceback
                    error_details = traceback.format_exc()
                    article_title = article_data.get('title', 'Unknown')
                    article_id = article_data.get('id', 'Unknown')
                    
                    print(f"❌ Fehler beim Importieren von Blog-Post '{article_title}' (ID: {article_id}): {e}")
                    print(f"Vollständiger Fehler: {error_details}")
                    
                    # Sammle detaillierte Fehlerinformationen
                    error_info = {
                        'article_id': article_id,
                        'article_title': article_title,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'error_details': error_details
                    }
                    
                    # Speichere den Fehler im Log für spätere Analyse
                    if not hasattr(log, '_errors'):
                        log._errors = []
                    log._errors.append(error_info)
            
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = django_timezone.now()
            log.save()
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = django_timezone.now()
            log.save()
        
        return log
    
    def _delete_all_local_blog_posts(self, blog: ShopifyBlog):
        """Löscht alle lokalen Blog-Posts für diesen Blog"""
        from .models import ShopifyBlogPost
        deleted_count, _ = ShopifyBlogPost.objects.filter(blog=blog).delete()
        return deleted_count
    
    def _create_or_update_blog(self, blog_data: Dict) -> Tuple[ShopifyBlog, bool]:
        """Erstellt oder aktualisiert einen Blog"""
        shopify_id = str(blog_data['id'])
        
        defaults = {
            'title': blog_data.get('title', '')[:255],
            'handle': blog_data.get('handle', '')[:255],
            'shopify_created_at': self._parse_shopify_datetime(blog_data.get('created_at')),
            'shopify_updated_at': self._parse_shopify_datetime(blog_data.get('updated_at')),
            'raw_shopify_data': blog_data,
        }
        
        blog, created = ShopifyBlog.objects.update_or_create(
            shopify_id=shopify_id,
            store=self.store,
            defaults=defaults
        )
        
        return blog, created
    
    def _create_or_update_blog_post(self, blog: ShopifyBlog, article_data: Dict) -> Tuple[ShopifyBlogPost, bool]:
        """Erstellt oder aktualisiert einen Blog-Post"""
        shopify_id = str(article_data['id'])
        
        # Extrahiere Featured Image
        featured_image_url = ""
        featured_image_alt = ""
        image_data = article_data.get('image')
        if image_data:
            # Debug: Zeige verfügbare Image-Felder
            print(f"Blog-Post {shopify_id} - Image data keys: {list(image_data.keys()) if isinstance(image_data, dict) else 'Not a dict'}")
            featured_image_url = image_data.get('src', '') or image_data.get('url', '')
            featured_image_alt = image_data.get('alt', '')
            print(f"Blog-Post {shopify_id} - Featured image URL: {featured_image_url[:100] if featured_image_url else 'None'}")
        
        # Parse published_at
        published_at = None
        if article_data.get('published_at'):
            published_at = self._parse_shopify_datetime(article_data['published_at'])
        
        # Shopify Blog API liefert kein 'status' Feld, sondern nur 'published_at'
        # Bestimme Status anhand des published_at Datums
        from django.utils import timezone
        
        if published_at:
            # Wenn published_at vorhanden und in der Vergangenheit = published
            if published_at <= timezone.now():
                final_status = 'published'
            else:
                # Zukünftiges Veröffentlichungsdatum = draft
                final_status = 'draft'
        else:
            # Kein published_at = draft
            final_status = 'draft'
        
        print(f"Blog-Post {shopify_id} Status bestimmt: '{final_status}' (published_at: {published_at})")
        
        defaults = {
            'title': article_data.get('title', '')[:255],
            'handle': article_data.get('handle', '')[:255],
            'content': article_data.get('body_html', '') or article_data.get('content', ''),
            'summary': article_data.get('summary_html', '') or article_data.get('summary', ''),
            'author': article_data.get('author', '')[:255],
            'status': final_status,
            'featured_image_url': featured_image_url,
            'featured_image_alt': featured_image_alt[:255],
            'tags': article_data.get('tags', ''),
            'published_at': published_at,
            'shopify_created_at': self._parse_shopify_datetime(article_data.get('created_at')),
            'shopify_updated_at': self._parse_shopify_datetime(article_data.get('updated_at')),
            'raw_shopify_data': article_data,
        }
        
        post, created = ShopifyBlogPost.objects.update_or_create(
            shopify_id=shopify_id,
            blog=blog,
            defaults=defaults
        )
        
        # Hole SEO-Daten über Metafields
        try:
            self._fetch_and_update_blog_post_seo_data(post)
        except Exception as e:
            print(f"Warnung: Konnte SEO-Daten für Blog-Post {post.shopify_id} nicht abrufen: {e}")
        
        return post, created
    
    def _fetch_and_update_blog_post_seo_data(self, post: ShopifyBlogPost):
        """Holt SEO-Daten für Blog-Posts über Metafields"""
        try:
            success, metafields, message = self.api.get_article_metafields(
                post.blog.shopify_id, 
                post.shopify_id
            )
            
            if success and metafields and isinstance(metafields, list):
                seo_title = ""
                seo_description = ""
                
                for metafield in metafields:
                    if not isinstance(metafield, dict):
                        continue
                        
                    namespace = metafield.get('namespace', '')
                    key = metafield.get('key', '')
                    value = str(metafield.get('value', ''))
                    
                    # SEO Title Patterns
                    if (namespace == 'global' and key == 'title_tag') or \
                       (namespace == 'seo' and key in ['title', 'meta_title']) or \
                       (key in ['meta_title', 'seo_title', 'title_tag']):
                        if value and not seo_title:
                            seo_title = value
                    
                    # SEO Description Patterns
                    if (namespace == 'global' and key == 'description_tag') or \
                       (namespace == 'seo' and key in ['description', 'meta_description']) or \
                       (key in ['meta_description', 'seo_description', 'description_tag']):
                        if value and not seo_description:
                            seo_description = value
                
                # Update Blog-Post
                updated = False
                if seo_title and seo_title != post.seo_title:
                    post.seo_title = seo_title[:70]
                    updated = True
                    
                if seo_description and seo_description != post.seo_description:
                    post.seo_description = seo_description[:160]
                    updated = True
                
                if updated:
                    post.save(update_fields=['seo_title', 'seo_description'])
                    print(f"SEO-Daten für Blog-Post {post.shopify_id} gespeichert")
                    
        except Exception as e:
            print(f"Fehler beim SEO-Daten-Abruf für Blog-Post: {e}")
    
    def _parse_shopify_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Konvertiert Shopify DateTime String zu Python datetime"""
        if not datetime_str:
            return None
        
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None


class ShopifyCollectionSync:
    """Synchronisation für Collections (Kategorien)"""
    
    def __init__(self, store: ShopifyStore):
        self.store = store
        self.api = ShopifyAPIClient(store)
    
    def _fetch_all_collections(self) -> Tuple[bool, List[Dict], str]:
        """Holt alle Collections über Pagination"""
        all_collections = []
        since_id = None
        total_fetched = 0
        
        while True:
            success, collections, message = self.api.fetch_collections(limit=250, since_id=since_id)
            
            if not success:
                return False, [], message
            
            if not collections:  # Keine weiteren Collections
                break
                
            all_collections.extend(collections)
            total_fetched += len(collections)
            print(f"📂 Collection Pagination: {len(collections)} Collections geholt, insgesamt: {total_fetched}")
            
            # since_id für nächste Seite setzen
            since_id = str(collections[-1]['id'])  # ID der letzten Collection
            
            # Nur stoppen wenn weniger als 250 Collections zurückgegeben wurden
            if len(collections) < 250:  # Weniger als Maximum = letzte Seite
                break
            
            # Sicherheitscheck: Stoppe bei sehr vielen Collections
            if total_fetched >= 10000:
                print(f"Sicherheitsstopp bei {total_fetched} Collections erreicht")
                break
        
        return True, all_collections, f"{total_fetched} Collections über Pagination abgerufen"
    
    def import_collections(self, limit: int = 250, import_mode: str = 'all', 
                          overwrite_existing: bool = True) -> ShopifySyncLog:
        """Importiert Collections von Shopify"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_collections',
            status='success'
        )
        
        try:
            # Bei "Alle Collections" mit "Überschreiben" - alle lokalen Collections löschen
            if import_mode == 'all' and overwrite_existing:
                deleted_count = self._delete_all_local_collections()
                print(f"🗑️ {deleted_count} lokale Collections gelöscht vor Neuimport")
            
            # Bei "Alle Collections" alle über Pagination holen, sonst nur bis zum Limit
            if import_mode == 'all':
                success, collections, message = self._fetch_all_collections()
            else:
                success, collections, message = self.api.fetch_collections(limit=limit)
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = django_timezone.now()
                log.save()
                return log
            
            log.products_processed = len(collections)
            success_count = 0
            failed_count = 0
            
            for collection_data in collections:
                try:
                    shopify_id = str(collection_data.get('id'))
                    
                    # Prüfe ob Collection bereits existiert (für new_only Modus)
                    existing_collection = None
                    if import_mode == 'new_only':
                        try:
                            existing_collection = ShopifyCollection.objects.get(
                                shopify_id=shopify_id, 
                                store=self.store
                            )
                            # Collection existiert bereits - überspringen
                            print(f"Collection {shopify_id} bereits vorhanden - überspringe (new_only Modus)")
                            continue
                        except ShopifyCollection.DoesNotExist:
                            # Collection existiert noch nicht - kann importiert werden
                            pass
                    
                    # Debug: Erste paar Collections ausgeben um Struktur zu verstehen
                    if success_count < 2:
                        print(f"Debug - Shopify Collection-Daten für ID {shopify_id}:")
                        print(f"  Verfügbare Keys: {list(collection_data.keys())}")
                        if 'image' in collection_data:
                            print(f"  Image Daten: {collection_data['image']}")
                        if 'seo_title' in collection_data:
                            print(f"  SEO Title: {collection_data['seo_title']}")
                        if 'seo_description' in collection_data:
                            print(f"  SEO Description: {collection_data['seo_description']}")
                    
                    # Collection erstellen oder aktualisieren
                    if import_mode == 'all' or existing_collection is None:
                        collection, created = self._create_or_update_collection(
                            collection_data, 
                            overwrite_existing=overwrite_existing
                        )
                        success_count += 1
                        if created:
                            print(f"Collection {shopify_id} erstellt: {collection.title}")
                            if success_count < 3:
                                print(f"  SEO Titel: '{collection.seo_title}'")
                                print(f"  SEO Beschreibung: '{collection.seo_description}'")
                        else:
                            print(f"Collection {shopify_id} aktualisiert: {collection.title}")
                            
                except Exception as e:
                    failed_count += 1
                    import traceback
                    error_details = traceback.format_exc()
                    collection_title = collection_data.get('title', 'Unknown')
                    collection_id = collection_data.get('id', 'Unknown')
                    
                    print(f"❌ Fehler beim Importieren von Collection '{collection_title}' (ID: {collection_id}): {e}")
                    print(f"Vollständiger Fehler: {error_details}")
                    
                    # Sammle detaillierte Fehlerinformationen
                    error_info = {
                        'collection_id': collection_id,
                        'collection_title': collection_title,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'error_details': error_details
                    }
                    
                    # Speichere den Fehler im Log für spätere Analyse
                    if not hasattr(log, '_errors'):
                        log._errors = []
                    log._errors.append(error_info)
            
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = django_timezone.now()
            log.save()
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = django_timezone.now()
            log.save()
        
        return log
    
    def _delete_all_local_collections(self):
        """Löscht alle lokalen Collections für diesen Store"""
        deleted_count, _ = ShopifyCollection.objects.filter(store=self.store).delete()
        return deleted_count
    
    def sync_collection_to_shopify(self, collection: ShopifyCollection) -> Tuple[bool, str]:
        """Synchronisiert eine lokale Collection zurück zu Shopify"""
        try:
            collection_data = {
                'title': collection.title,
                'description': collection.description,
                'published': collection.published,
                'sort_order': collection.sort_order,
                'seo_title': collection.seo_title,
                'seo_description': collection.seo_description,
            }
            
            # Image-Daten falls vorhanden
            if collection.image_url:
                collection_data['image'] = {
                    'src': collection.image_url,
                    'alt': collection.image_alt
                }
            
            success, updated_collection, message = self.api.update_collection(
                collection.shopify_id, 
                collection_data,
                seo_only=True  # Nur SEO-Metafields aktualisieren
            )
            
            if success:
                # Update lokale Collection mit Shopify Daten
                collection.last_synced_at = django_timezone.now()
                collection.needs_sync = False
                collection.sync_error = ""
                
                if updated_collection:
                    collection.shopify_updated_at = self._parse_shopify_datetime(
                        updated_collection.get('updated_at')
                    )
                
                collection.save()
                return True, "Erfolgreich synchronisiert"
            else:
                collection.sync_error = message
                collection.save()
                return False, message
                
        except Exception as e:
            error_msg = f"Sync-Fehler: {str(e)}"
            collection.sync_error = error_msg
            collection.save()
            return False, error_msg
    
    def _create_or_update_collection(self, collection_data: Dict, overwrite_existing: bool = True) -> Tuple[ShopifyCollection, bool]:
        """Erstellt oder aktualisiert eine lokale Collection basierend auf Shopify Daten"""
        shopify_id = str(collection_data['id'])
        
        # Extrahiere Bild-Daten
        image_url = ""
        image_alt = ""
        if 'image' in collection_data and collection_data['image']:
            image_data = collection_data['image']
            image_url = image_data.get('src', '') or image_data.get('url', '')
            image_alt = image_data.get('alt', '')
        
        # Hole SEO Daten aus Shopify Collection-Daten
        seo_title = ""
        seo_description = ""
        
        # Shopify speichert SEO-Daten manchmal im Hauptobjekt
        if 'seo_title' in collection_data:
            seo_title = collection_data.get('seo_title', '')
        if 'seo_description' in collection_data:
            seo_description = collection_data.get('seo_description', '')
            
        # Fallback: Titel als SEO-Titel verwenden falls leer
        if not seo_title:
            seo_title = collection_data.get('title', '')[:70]
        
        # Prüfe ob Collection bereits existiert (für overwrite_existing Check)
        existing_collection = None
        try:
            existing_collection = ShopifyCollection.objects.get(shopify_id=shopify_id, store=self.store)
        except ShopifyCollection.DoesNotExist:
            pass
        
        # Wenn Collection existiert und overwrite_existing=False, dann überspringen
        if existing_collection and not overwrite_existing:
            print(f"Collection {shopify_id} existiert bereits und overwrite_existing=False - überspringe")
            return existing_collection, False
        
        # Erstelle oder aktualisiere Collection
        try:
            defaults = {
                'title': collection_data.get('title', '')[:255],  # Titel begrenzen
                'handle': collection_data.get('handle', '')[:255],  # Handle begrenzen
                'description': collection_data.get('body_html') or collection_data.get('description') or '',
                'seo_title': seo_title[:70] if seo_title else '',  # SEO Titel begrenzen
                'seo_description': seo_description[:160] if seo_description else '',  # SEO Beschreibung begrenzen
                'image_url': image_url,
                'image_alt': image_alt[:255] if image_alt else '',  # Alt Text begrenzen
                'sort_order': collection_data.get('sort_order', 'best-selling'),
                'published': collection_data.get('published', True),
                'collection_type': collection_data.get('collection_type', 'custom'),  # Neues Feld hinzufügen
                'shopify_created_at': self._parse_shopify_datetime(collection_data.get('created_at')),
                'shopify_updated_at': self._parse_shopify_datetime(collection_data.get('updated_at')),
                'last_synced_at': django_timezone.now(),
                'needs_sync': False,
                'raw_shopify_data': collection_data,
            }
            
            collection, created = ShopifyCollection.objects.update_or_create(
                shopify_id=shopify_id,
                store=self.store,
                defaults=defaults
            )
        except Exception as e:
            print(f"Fehler bei update_or_create für Collection {shopify_id}: {e}")
            print(f"Collection-Daten: {collection_data}")
            raise
        
        # Hole SEO-Daten über Metafields für ALLE Collections (nicht nur neue)
        try:
            self._fetch_and_update_seo_data(collection)
        except Exception as e:
            print(f"Warnung: Konnte SEO-Daten für Collection {collection.shopify_id} nicht abrufen: {e}")
        
        return collection, created
    
    def _fetch_and_update_seo_data(self, collection: ShopifyCollection):
        """Holt SEO-Daten über Metafields API"""
        try:
            success, metafields, message = self.api.get_collection_metafields(collection.shopify_id)
            
            print(f"Metafields-Abruf für Collection {collection.shopify_id}: {success}")
            print(f"Metafields Typ: {type(metafields)}")
            print(f"Metafields Inhalt: {metafields}")
            print(f"Message: {message}")
            
        except Exception as e:
            print(f"Fehler beim Metafields-Abruf: {e}")
            return
        
        if success and metafields and isinstance(metafields, list):
            seo_title = ""
            seo_description = ""
            
            print(f"Verfügbare Metafields: {[(m.get('namespace', ''), m.get('key', ''), str(m.get('value', ''))[:50]) for m in metafields if isinstance(m, dict)]}")
            
            for metafield in metafields:
                if not isinstance(metafield, dict):
                    print(f"Warnung: Metafield ist kein Dict: {type(metafield)} = {metafield}")
                    continue
                    
                namespace = metafield.get('namespace', '')
                key = metafield.get('key', '')
                value = str(metafield.get('value', ''))
                
                print(f"Prüfe Metafield: {namespace}.{key} = '{value[:50]}...'")
                
                # SEO Metafield Patterns - GLOBAL NAMESPACE hat höchste Priorität
                title_patterns = [
                    # HÖCHSTE PRIORITÄT: Global Namespace (von Webrex SEO AI Optimizer verwendet)
                    (namespace == 'global' and key == 'title_tag'),
                    # Standard SEO Fields 
                    (namespace == 'seo' and key == 'title'),
                    (namespace == 'seo' and key == 'meta_title'),
                    (namespace == 'custom' and key == 'meta_title'),
                    (key == 'meta_title'),
                    (key == 'seo_title'),
                    (key == 'title_tag'),
                    # Shopify Standard SEO
                    (namespace == 'descriptors' and key == 'title'),
                    (namespace == 'shopify' and key == 'seo_title'),
                ]
                
                description_patterns = [
                    # HÖCHSTE PRIORITÄT: Global Namespace (von Webrex SEO AI Optimizer verwendet)
                    (namespace == 'global' and key == 'description_tag'),
                    # Standard SEO Fields
                    (namespace == 'seo' and key == 'description'),
                    (namespace == 'seo' and key == 'meta_description'),
                    (namespace == 'custom' and key == 'meta_description'),
                    (key == 'meta_description'),
                    (key == 'seo_description'),
                    (key == 'description_tag'),
                    # Shopify Standard SEO
                    (namespace == 'descriptors' and key == 'description'),
                    (namespace == 'shopify' and key == 'seo_description'),
                ]
                
                # Prüfe Title Patterns
                title_match = any(title_patterns)
                if title_match and value and not seo_title:
                    seo_title = value
                    print(f"✅ SEO-Titel gefunden: {namespace}.{key} = '{value[:50]}...'")
                elif title_match:
                    print(f"🔍 Title Pattern Match aber übersprungen: {namespace}.{key}, value='{value[:30]}...', bereits seo_title='{seo_title[:30] if seo_title else 'None'}...'")
                    
                # Prüfe Description Patterns
                description_match = any(description_patterns)
                if description_match and value and not seo_description:
                    seo_description = value
                    print(f"✅ SEO-Beschreibung gefunden: {namespace}.{key} = '{value[:50]}...'")
                elif description_match:
                    print(f"🔍 Description Pattern Match aber übersprungen: {namespace}.{key}, value='{value[:30]}...', bereits seo_description='{seo_description[:30] if seo_description else 'None'}...'")
                else:
                    print(f"❌ Kein Pattern Match für: {namespace}.{key}")
                
                # Fallback: Allgemeine SEO-Erkennung für unbekannte App-Strukturen
                if not seo_title and value:
                    key_lower = key.lower()
                    namespace_lower = namespace.lower()
                    # Suche nach Variationen von "title" in Kombination mit SEO-Keywords
                    if any(word in key_lower for word in ['title', 'headline']) and \
                       any(word in (key_lower + namespace_lower) for word in ['seo', 'meta', 'tag', 'webrex', 'optimizer']):
                        seo_title = value
                        print(f"✅ SEO-Titel (Fallback) gefunden: {namespace}.{key}")
                
                if not seo_description and value:
                    key_lower = key.lower()
                    namespace_lower = namespace.lower()
                    # Suche nach Variationen von "description" in Kombination mit SEO-Keywords
                    if any(word in key_lower for word in ['description', 'desc', 'summary']) and \
                       any(word in (key_lower + namespace_lower) for word in ['seo', 'meta', 'tag', 'webrex', 'optimizer']):
                        seo_description = value
                        print(f"✅ SEO-Beschreibung (Fallback) gefunden: {namespace}.{key}")
            
            # Update die Collection wenn SEO-Daten gefunden wurden
            updated = False
            if seo_title and seo_title != collection.seo_title:
                collection.seo_title = seo_title[:70]
                updated = True
                print(f"SEO-Titel aktualisiert: '{seo_title[:50]}...'")
                
            if seo_description and seo_description != collection.seo_description:
                collection.seo_description = seo_description[:160]
                updated = True
                print(f"SEO-Beschreibung aktualisiert: '{seo_description[:50]}...'")
            
            if updated:
                collection.save(update_fields=['seo_title', 'seo_description'])
                print(f"SEO-Daten für Collection {collection.shopify_id} gespeichert")
            else:
                print(f"Keine neuen SEO-Daten für Collection {collection.shopify_id}")
        else:
            print(f"Keine Metafields gefunden für Collection {collection.shopify_id}: {message}")
    
    def _parse_shopify_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Konvertiert Shopify DateTime String zu Python datetime"""
        if not datetime_str:
            return None
        
        try:
            # Shopify verwendet ISO 8601 Format
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
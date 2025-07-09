import requests
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from django.utils import timezone as django_timezone
from .models import ShopifyStore, ShopifyProduct, ShopifyProductImage, ShopifySyncLog, ShopifyBlog, ShopifyBlogPost


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
    
    def fetch_blog_posts(self, blog_id: str, limit: int = 250, since_id: Optional[str] = None) -> Tuple[bool, List[Dict], str]:
        """Holt Blog-Posts für einen bestimmten Blog"""
        try:
            # Hole alle Felder direkt in einer Abfrage (inkl. Content)
            params = {
                'limit': min(limit, 250),
                'fields': 'id,title,handle,author,status,created_at,updated_at,published_at,tags,image,body_html,summary'
            }
            
            if since_id:
                params['since_id'] = since_id
            
            response = self._make_request(
                'GET',
                f"{self.base_url}/blogs/{blog_id}/articles.json",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
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
                
                return True, enhanced_articles, f"{len(enhanced_articles)} Blog-Posts abgerufen"
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, [], f"Fehler beim Abrufen der Blog-Posts: {str(e)}"
    
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
                
                return seo_success, updated_article, final_message
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Blog-Post Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except requests.exceptions.RequestException as e:
            return False, None, f"Fehler beim Update des Blog-Posts: {str(e)}"
    
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
            if len(products) < 250:  # Weniger als Maximum = letzte Seite
                break
            
            since_id = str(products[-1]['id'])  # ID des letzten Produkts
            
            # Sicherheitscheck: Stoppe bei sehr vielen Produkten
            if total_fetched >= 50000:
                print(f"Sicherheitsstopp bei {total_fetched} Produkten erreicht")
                break
        
        return True, all_products, f"{total_fetched} Produkte über Pagination abgerufen"
    
    def import_products(self, limit: int = 250, import_mode: str = 'all', 
                       overwrite_existing: bool = True, import_images: bool = True) -> ShopifySyncLog:
        """Importiert Produkte von Shopify"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import',
            status='success'
        )
        
        try:
            # Bei "Alle Produkte" mit "Überschreiben" - alle lokalen Produkte löschen
            if import_mode == 'all' and overwrite_existing:
                deleted_count = self._delete_all_local_products()
                print(f"🗑️ {deleted_count} lokale Produkte gelöscht vor Neuimport")
            
            # Bei "Alle Produkte" alle über Pagination holen, sonst nur bis zum Limit
            if import_mode == 'all':
                success, products, message = self._fetch_all_products()
            else:
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
            
            for product_data in products:
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
                    
                    # Produkt erstellen oder aktualisieren
                    if import_mode == 'all' or existing_product is None:
                        product, created = self._create_or_update_product(
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
        
        # Extrahiere Preis aus Varianten
        price = None
        compare_at_price = None
        variants = product_data.get('variants', [])
        if variants:
            first_variant = variants[0]
            try:
                price_str = first_variant.get('price')
                if price_str:
                    from decimal import Decimal
                    price = Decimal(str(price_str))
            except (ValueError, TypeError):
                price = None
            
            try:
                compare_price_str = first_variant.get('compare_at_price')
                if compare_price_str:
                    from decimal import Decimal
                    compare_at_price = Decimal(str(compare_price_str))
            except (ValueError, TypeError):
                compare_at_price = None
        
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
            defaults = {
                'title': product_data.get('title', '')[:255],  # Titel begrenzen
                'handle': product_data.get('handle', '')[:255],  # Handle begrenzen
                'body_html': product_data.get('body_html') or '',
                'vendor': product_data.get('vendor', '')[:255],  # Vendor begrenzen  
                'product_type': product_data.get('product_type', '')[:255],  # Product Type begrenzen
                'status': product_data.get('status', 'active'),
                'seo_title': seo_title[:70] if seo_title else '',  # SEO Titel begrenzen
                'seo_description': seo_description[:160] if seo_description else '',  # SEO Beschreibung begrenzen
                'featured_image_url': featured_image_url,
                'featured_image_alt': featured_image_alt[:255] if featured_image_alt else '',  # Alt Text begrenzen
                'price': price,
                'compare_at_price': compare_at_price,
                'tags': product_data.get('tags') or '',
                'shopify_created_at': self._parse_shopify_datetime(product_data.get('created_at')),
                'shopify_updated_at': self._parse_shopify_datetime(product_data.get('updated_at')),
                'last_synced_at': django_timezone.now(),
                'needs_sync': False,
                'raw_shopify_data': product_data,
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
    
    def _create_product_images(self, product: ShopifyProduct, images: List[Dict]):
        """Erstellt Produktbilder für ein Produkt"""
        # Lösche bestehende Bilder
        product.images.all().delete()
        
        for i, image_data in enumerate(images):
            ShopifyProductImage.objects.create(
                product=product,
                shopify_image_id=str(image_data.get('id', '')),
                image_url=image_data.get('src', ''),
                alt_text=image_data.get('alt', ''),
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
        """Holt alle Blog-Posts über Pagination"""
        all_articles = []
        since_id = None
        total_fetched = 0

        while True:
            # Hier wird die API-Client-Methode aufgerufen
            success, articles, message = self.api.fetch_blog_posts(blog_id, limit=250, since_id=since_id)

            if not success:
                return False, [], message

            if not articles:  # Keine weiteren Artikel
                break

            all_articles.extend(articles)
            total_fetched += len(articles)
            print(f"📄 Blog-Post Pagination: {len(articles)} Blog-Posts geholt, insgesamt: {total_fetched}")

            # since_id für nächste Seite setzen
            if len(articles) < 250:  # Weniger als Maximum = letzte Seite
                break

            since_id = str(articles[-1]['id'])  # ID des letzten Artikels

            # Sicherheitscheck: Stoppe bei sehr vielen Artikeln
            if total_fetched >= 50000:
                print(f"Sicherheitsstopp bei {total_fetched} Blog-Posts erreicht")
                break

        return True, all_articles, f"{total_fetched} Blog-Posts über Pagination abgerufen"

    def import_blog_posts(self, blog: ShopifyBlog, import_mode: str = 'new_only') -> ShopifySyncLog:
        """Importiert Blog-Posts für einen bestimmten Blog"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_blog_posts',
            status='success'
        )
        
        try:
            # Bei "Alle Posts" - alle lokalen Blog-Posts für diesen Blog löschen
            if import_mode == 'all':
                deleted_count = self._delete_all_local_blog_posts(blog)
                print(f"🗑️ {deleted_count} lokale Blog-Posts gelöscht vor Neuimport für Blog {blog.title}")
            
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
            
            for article_data in articles:
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
                    if created:
                        print(f"Blog-Post {post.shopify_id} erstellt: {post.title}")
                    else:
                        print(f"Blog-Post {post.shopify_id} aktualisiert: {post.title}")
                        
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
            featured_image_url = image_data.get('url', '') or image_data.get('src', '')
            featured_image_alt = image_data.get('alt', '')
        
        # Parse published_at
        published_at = None
        if article_data.get('published_at'):
            published_at = self._parse_shopify_datetime(article_data['published_at'])
        
        # Debug: Status von Shopify ausgeben
        shopify_status = article_data.get('status', 'draft')
        print(f"Blog-Post {shopify_id} Status von Shopify: '{shopify_status}', Published: {article_data.get('published_at')}")
        
        # Smart Status Detection: Wenn ein Post ein published_at Datum hat und es in der Vergangenheit liegt,
        # behandle ihn als veröffentlicht, auch wenn Shopify ihn als "draft" markiert
        final_status = shopify_status
        if shopify_status == 'draft' and published_at:
            from django.utils import timezone
            if published_at <= timezone.now():
                final_status = 'published'
                print(f"Blog-Post {shopify_id} Status korrigiert: 'draft' -> 'published' (aufgrund published_at)")
        
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
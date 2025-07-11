"""
Shopify Integration Service for Image Editor
Ermöglicht den Import und Export von Bildern zwischen Shopify und dem Bildeditor
"""

import requests
import tempfile
import os
from typing import List, Dict, Optional, Tuple
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from shopify_manager.models import ShopifyStore
from shopify_manager.shopify_api import ShopifyAPIClient


class ShopifyImageService:
    """Service für Shopify Bild-Import und Export"""
    
    def __init__(self, store: ShopifyStore):
        self.store = store
        self.api_client = ShopifyAPIClient(store)
    
    def get_product_images(self, limit: int = 50) -> Tuple[bool, List[Dict], str]:
        """Holt Produktbilder von Shopify"""
        try:
            # Produkte mit Bildern abrufen
            success, products, error = self.api_client.fetch_products(limit=limit)
            
            if not success:
                return False, [], error
            
            images = []
            for product in products:
                product_images = product.get('images', [])
                for img in product_images:
                    images.append({
                        'id': img.get('id'),
                        'product_id': product.get('id'),
                        'product_title': product.get('title'),
                        'src': img.get('src'),
                        'alt': img.get('alt', ''),
                        'width': img.get('width'),
                        'height': img.get('height'),
                        'created_at': img.get('created_at'),
                        'updated_at': img.get('updated_at')
                    })
            
            return True, images, f"{len(images)} Bilder gefunden"
            
        except Exception as e:
            return False, [], f"Fehler beim Abrufen der Bilder: {str(e)}"
    
    def download_image(self, image_url: str, alt_text: str = "") -> Tuple[bool, Optional[str], str]:
        """Lädt ein Bild von Shopify herunter und speichert es lokal"""
        try:
            # Bild herunterladen
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Temporäre Datei erstellen
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            # Bild mit PIL öffnen und validieren
            try:
                with Image.open(temp_path) as img:
                    # Bild konvertieren falls nötig
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGB')
                    
                    # Eindeutigen Dateinamen generieren
                    import uuid
                    filename = f"shopify_import_{uuid.uuid4().hex[:8]}.jpg"
                    
                    # Bild in Media-Ordner speichern
                    with open(temp_path, 'rb') as f:
                        file_content = ContentFile(f.read(), name=filename)
                        saved_path = default_storage.save(f"image_editor/imports/{filename}", file_content)
                    
                    # Temporäre Datei löschen
                    os.unlink(temp_path)
                    
                    return True, saved_path, f"Bild erfolgreich importiert: {filename}"
                    
            except Exception as img_error:
                os.unlink(temp_path)
                return False, None, f"Bildverarbeitungsfehler: {str(img_error)}"
            
        except requests.exceptions.RequestException as e:
            return False, None, f"Download-Fehler: {str(e)}"
        except Exception as e:
            return False, None, f"Unerwarteter Fehler: {str(e)}"
    
    def upload_image_to_product(self, image_path: str, product_id: str, alt_text: str = "") -> Tuple[bool, Optional[Dict], str]:
        """Lädt ein Bild zu einem Shopify-Produkt hoch"""
        try:
            # Bild laden und als Base64 kodieren
            import base64
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Dateiname extrahieren
            filename = os.path.basename(image_path)
            
            # Bild-Daten für Shopify API vorbereiten
            image_payload = {
                "image": {
                    "attachment": image_data,
                    "filename": filename,
                    "alt": alt_text
                }
            }
            
            # API-Aufruf
            response = requests.post(
                f"{self.store.get_api_url()}/products/{product_id}/images.json",
                headers=self.api_client.headers,
                json=image_payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                image_data = response.json().get('image', {})
                return True, image_data, "Bild erfolgreich zu Produkt hinzugefügt"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Upload fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except Exception as e:
            return False, None, f"Fehler beim Upload: {str(e)}"
    
    def create_product_with_image(self, image_path: str, product_title: str, product_description: str = "", alt_text: str = "") -> Tuple[bool, Optional[Dict], str]:
        """Erstellt ein neues Produkt mit einem Bild"""
        try:
            # Bild laden und als Base64 kodieren
            import base64
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            filename = os.path.basename(image_path)
            
            # Produkt-Daten vorbereiten
            product_payload = {
                "product": {
                    "title": product_title,
                    "body_html": product_description,
                    "status": "draft",
                    "images": [{
                        "attachment": image_data,
                        "filename": filename,
                        "alt": alt_text
                    }]
                }
            }
            
            # API-Aufruf
            response = requests.post(
                f"{self.store.get_api_url()}/products.json",
                headers=self.api_client.headers,
                json=product_payload,
                timeout=30
            )
            
            if response.status_code == 201:
                product_data = response.json().get('product', {})
                return True, product_data, f"Produkt '{product_title}' erfolgreich erstellt"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Produkterstellung fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except Exception as e:
            return False, None, f"Fehler bei der Produkterstellung: {str(e)}"
    
    def get_products_for_export(self, limit: int = 250) -> Tuple[bool, List[Dict], str]:
        """Holt Produkte für Export-Auswahl"""
        try:
            success, products, error = self.api_client.fetch_products(limit=limit)
            
            if not success:
                return False, [], error
            
            # Vereinfachte Produktliste für Export
            simplified_products = []
            for product in products:
                simplified_products.append({
                    'id': product.get('id'),
                    'title': product.get('title'),
                    'handle': product.get('handle'),
                    'status': product.get('status'),
                    'image_count': len(product.get('images', [])),
                    'created_at': product.get('created_at'),
                    'updated_at': product.get('updated_at')
                })
            
            return True, simplified_products, f"{len(simplified_products)} Produkte gefunden"
            
        except Exception as e:
            return False, [], f"Fehler beim Abrufen der Produkte: {str(e)}"
    
    def search_products_for_export(self, search_term: str, limit: int = 50) -> Tuple[bool, List[Dict], str]:
        """Sucht Produkte für Export-Auswahl"""
        try:
            success, products, error = self.api_client.search_products(search_term=search_term, limit=limit)
            
            if not success:
                return False, [], error
            
            # Vereinfachte Produktliste für Export
            simplified_products = []
            for product in products:
                simplified_products.append({
                    'id': product.get('id'),
                    'title': product.get('title'),
                    'handle': product.get('handle'),
                    'status': product.get('status'),
                    'image_count': len(product.get('images', [])),
                    'created_at': product.get('created_at'),
                    'updated_at': product.get('updated_at')
                })
            
            return True, simplified_products, f"{len(simplified_products)} Produkte für '{search_term}' gefunden"
            
        except Exception as e:
            return False, [], f"Fehler bei der Produktsuche: {str(e)}"
    
    def update_product_image(self, product_id: str, image_id: str, image_path: str, alt_text: str = "") -> Tuple[bool, Optional[Dict], str]:
        """Aktualisiert ein bestehendes Produktbild"""
        try:
            # Bild laden und als Base64 kodieren
            import base64
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            filename = os.path.basename(image_path)
            
            # Update-Daten vorbereiten
            image_payload = {
                "image": {
                    "id": int(image_id),
                    "attachment": image_data,
                    "filename": filename,
                    "alt": alt_text
                }
            }
            
            # API-Aufruf
            response = requests.put(
                f"{self.store.get_api_url()}/products/{product_id}/images/{image_id}.json",
                headers=self.api_client.headers,
                json=image_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                image_data = response.json().get('image', {})
                return True, image_data, "Bild erfolgreich aktualisiert"
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                return False, None, f"Update fehlgeschlagen - HTTP {response.status_code}: {error_data}"
                
        except Exception as e:
            return False, None, f"Fehler beim Update: {str(e)}"
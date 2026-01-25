"""
P-Loom Shopify Service für Produkt-Upload
"""
import base64
import logging
import requests
import time
from typing import Tuple, Optional, Dict, List
from urllib.request import urlopen

logger = logging.getLogger(__name__)


class PLoomShopifyService:
    """Service für Shopify-Produkt-Upload"""

    def __init__(self, store):
        """
        Initialisiert den Service mit einem ShopifyStore

        Args:
            store: ShopifyStore-Instanz
        """
        self.store = store
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

    def create_draft_product(self, ploom_product) -> Tuple[bool, str, str]:
        """
        Erstellt ein Produkt als Entwurf in Shopify

        Args:
            ploom_product: PLoomProduct-Instanz

        Returns:
            Tuple[bool, str, str]: (success, shopify_product_id, error_message)
        """
        try:
            # Produktdaten aufbauen
            product_data = {
                "product": {
                    "title": ploom_product.title,
                    "body_html": ploom_product.description,
                    "vendor": ploom_product.vendor or "",
                    "product_type": ploom_product.product_type or "",
                    "tags": ploom_product.tags or "",
                    "status": "draft",  # Immer als Entwurf
                }
            }

            # Template Suffix (Theme-Vorlage)
            if ploom_product.template_suffix:
                product_data["product"]["template_suffix"] = ploom_product.template_suffix

            # SEO-Daten
            if ploom_product.seo_title or ploom_product.seo_description:
                product_data["product"]["metafields_global_title_tag"] = ploom_product.seo_title or ""
                product_data["product"]["metafields_global_description_tag"] = ploom_product.seo_description or ""

            # Varianten
            variants = list(ploom_product.variants.all())
            if variants:
                product_data["product"]["variants"] = []

                # Optionen sammeln
                options = set()
                for variant in variants:
                    if variant.option1_name:
                        options.add(variant.option1_name)
                    if variant.option2_name:
                        options.add(variant.option2_name)
                    if variant.option3_name:
                        options.add(variant.option3_name)

                if options:
                    product_data["product"]["options"] = [{"name": opt} for opt in list(options)[:3]]

                for variant in variants:
                    variant_data = {
                        "title": str(variant),
                        "price": str(variant.price) if variant.price else str(ploom_product.price or "0.00"),
                        "sku": variant.sku or "",
                        "inventory_quantity": variant.inventory_quantity,
                        "inventory_policy": variant.inventory_policy,
                        "requires_shipping": variant.requires_shipping,
                        "taxable": variant.taxable,
                    }

                    if variant.compare_at_price:
                        variant_data["compare_at_price"] = str(variant.compare_at_price)

                    if variant.option1_value:
                        variant_data["option1"] = variant.option1_value
                    if variant.option2_value:
                        variant_data["option2"] = variant.option2_value
                    if variant.option3_value:
                        variant_data["option3"] = variant.option3_value

                    if variant.barcode:
                        variant_data["barcode"] = variant.barcode

                    if variant.weight:
                        variant_data["weight"] = float(variant.weight)
                        variant_data["weight_unit"] = variant.weight_unit

                    product_data["product"]["variants"].append(variant_data)
            else:
                # Keine Varianten = Standard-Variante mit Produktpreis
                product_data["product"]["variants"] = [{
                    "price": str(ploom_product.price or "0.00"),
                    "inventory_policy": "deny",
                    "requires_shipping": True,
                    "taxable": True,
                }]

                if ploom_product.compare_at_price:
                    product_data["product"]["variants"][0]["compare_at_price"] = str(ploom_product.compare_at_price)

                # Gewicht hinzufügen
                if ploom_product.weight:
                    product_data["product"]["variants"][0]["weight"] = float(ploom_product.weight)
                    product_data["product"]["variants"][0]["weight_unit"] = ploom_product.weight_unit

            # Produkt erstellen
            response = self._make_request(
                'POST',
                f"{self.base_url}/products.json",
                json=product_data,
                timeout=30
            )

            if response.status_code in [200, 201]:
                data = response.json()
                shopify_product_id = str(data.get('product', {}).get('id', ''))

                # Bilder hochladen
                images = list(ploom_product.images.all())
                if images:
                    self._upload_product_images(shopify_product_id, images)

                # Metafelder setzen
                if ploom_product.product_metafields:
                    self._set_product_metafields(shopify_product_id, ploom_product.product_metafields)

                # Collection zuweisen
                if ploom_product.collection_id:
                    self._add_product_to_collection(shopify_product_id, ploom_product.collection_id)

                # Vertriebskanäle zuweisen
                if ploom_product.sales_channels:
                    self.publish_to_channels(shopify_product_id, ploom_product.sales_channels)

                return True, shopify_product_id, ""
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to create product: {error_msg}")
                return False, "", error_msg

        except Exception as e:
            logger.error(f"Error creating product: {e}")
            return False, "", str(e)

    def _upload_product_images(self, product_id: str, images: list) -> None:
        """Lädt Bilder zu einem Produkt hoch"""
        for i, image in enumerate(images):
            try:
                image_url = image.image_url
                if not image_url:
                    continue

                # Bild-Daten vorbereiten
                image_data = {
                    "image": {
                        "position": i + 1,
                        "alt": image.alt_text or "",
                    }
                }

                # Wenn es eine URL ist, können wir sie direkt verwenden
                if image_url.startswith('http'):
                    image_data["image"]["src"] = image_url
                else:
                    # Lokales Bild - Base64 kodieren
                    try:
                        from django.conf import settings
                        import os

                        # Relativen Pfad zu absolutem konvertieren
                        if image_url.startswith('/'):
                            file_path = os.path.join(settings.BASE_DIR, image_url.lstrip('/'))
                        else:
                            file_path = image_url

                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                image_base64 = base64.b64encode(f.read()).decode('utf-8')
                                image_data["image"]["attachment"] = image_base64
                        else:
                            # Versuche mit MEDIA_ROOT
                            if image.source == 'upload' and image.image:
                                with open(image.image.path, 'rb') as f:
                                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
                                    image_data["image"]["attachment"] = image_base64
                            else:
                                logger.warning(f"Image file not found: {image_url}")
                                continue
                    except Exception as e:
                        logger.warning(f"Could not encode image: {e}")
                        continue

                response = self._make_request(
                    'POST',
                    f"{self.base_url}/products/{product_id}/images.json",
                    json=image_data,
                    timeout=60
                )

                if response.status_code not in [200, 201]:
                    logger.warning(f"Failed to upload image: {response.text}")

            except Exception as e:
                logger.warning(f"Error uploading image: {e}")
                continue

    def _set_product_metafields(self, product_id: str, metafields: Dict) -> None:
        """Setzt Metafelder für ein Produkt"""
        try:
            for key, value in metafields.items():
                # Namespace und Key aus dem Key extrahieren (Format: namespace.key)
                if '.' in key:
                    namespace, metafield_key = key.split('.', 1)
                else:
                    namespace = 'custom'
                    metafield_key = key

                metafield_data = {
                    "metafield": {
                        "namespace": namespace,
                        "key": metafield_key,
                        "value": str(value),
                        "type": "single_line_text_field"
                    }
                }

                response = self._make_request(
                    'POST',
                    f"{self.base_url}/products/{product_id}/metafields.json",
                    json=metafield_data,
                    timeout=10
                )

                if response.status_code not in [200, 201]:
                    logger.warning(f"Failed to set metafield {key}: {response.text}")

        except Exception as e:
            logger.warning(f"Error setting metafields: {e}")

    def _add_product_to_collection(self, product_id: str, collection_id: str) -> None:
        """Fügt ein Produkt einer Collection hinzu"""
        try:
            collect_data = {
                "collect": {
                    "product_id": int(product_id),
                    "collection_id": int(collection_id)
                }
            }

            response = self._make_request(
                'POST',
                f"{self.base_url}/collects.json",
                json=collect_data,
                timeout=10
            )

            if response.status_code not in [200, 201]:
                logger.warning(f"Failed to add product to collection: {response.text}")

        except Exception as e:
            logger.warning(f"Error adding product to collection: {e}")

    def get_publications(self) -> Tuple[bool, List[Dict], str]:
        """Holt alle Sales Channels / Veröffentlichungskanäle"""
        try:
            response = self._make_request(
                'GET',
                f"{self.base_url}/publications.json",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                publications = []
                for pub in data.get('publications', []):
                    publications.append({
                        'id': str(pub.get('id')),
                        'name': pub.get('name', 'Unbekannt'),
                        'handle': pub.get('handle', ''),
                    })
                return True, publications, ""
            else:
                return False, [], f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            logger.error(f"Error fetching publications: {e}")
            return False, [], str(e)

    def publish_to_channels(self, product_id: str, publication_ids: List[str]) -> None:
        """Veröffentlicht ein Produkt auf ausgewählten Kanälen"""
        for pub_id in publication_ids:
            try:
                publish_data = {
                    "product_publication": {
                        "publication_id": int(pub_id)
                    }
                }

                response = self._make_request(
                    'PUT',
                    f"{self.base_url}/products/{product_id}/publish.json",
                    json=publish_data,
                    timeout=10
                )

                if response.status_code not in [200, 201]:
                    # Fallback: ProductPublication API verwenden
                    response = self._make_request(
                        'POST',
                        f"{self.base_url}/products/{product_id}/product_publications.json",
                        json={"product_publication": {"publication_id": int(pub_id)}},
                        timeout=10
                    )

                    if response.status_code not in [200, 201]:
                        logger.warning(f"Failed to publish to channel {pub_id}: {response.text}")

            except Exception as e:
                logger.warning(f"Error publishing to channel {pub_id}: {e}")

    def get_collections(self) -> Tuple[bool, List[Dict], str]:
        """Holt alle Collections"""
        try:
            all_collections = []

            # Custom Collections
            response = self._make_request(
                'GET',
                f"{self.base_url}/custom_collections.json",
                params={'limit': 250},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                for collection in data.get('custom_collections', []):
                    all_collections.append({
                        'id': str(collection.get('id')),
                        'title': collection.get('title'),
                        'type': 'custom'
                    })

            # Smart Collections
            response = self._make_request(
                'GET',
                f"{self.base_url}/smart_collections.json",
                params={'limit': 250},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                for collection in data.get('smart_collections', []):
                    all_collections.append({
                        'id': str(collection.get('id')),
                        'title': collection.get('title'),
                        'type': 'smart'
                    })

            return True, all_collections, ""

        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return False, [], str(e)

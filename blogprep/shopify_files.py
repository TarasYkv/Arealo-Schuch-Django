"""
Shopify Files API Integration

Lädt Bilder zu Shopify hoch und gibt CDN-URLs zurück.
Verwendet die GraphQL Admin API.
"""

import logging
import base64
import requests
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class ShopifyFilesService:
    """Service für Shopify Files API Upload"""

    def __init__(self, store):
        """
        Initialisiert den Service mit einem ShopifyStore.

        Args:
            store: ShopifyStore Objekt mit shop_domain und access_token
        """
        self.store = store
        self.graphql_url = f"https://{store.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json'
        }

    def upload_image_from_base64(self, image_data: str, filename: str, alt_text: str = '') -> Tuple[bool, str, str]:
        """
        Lädt ein Base64-kodiertes Bild zu Shopify Files hoch.

        Args:
            image_data: Base64-kodierte Bilddaten (ohne data:image/... Prefix)
            filename: Dateiname für das Bild (ohne Extension)
            alt_text: Alt-Text für das Bild

        Returns:
            Tuple (success, cdn_url_or_error, file_id)
        """
        try:
            # Schritt 1: Staged Upload erstellen
            staged_result = self._create_staged_upload(filename)
            if not staged_result['success']:
                return False, staged_result['error'], ''

            staged_target = staged_result['staged_target']
            resource_url = staged_result['resource_url']

            # Schritt 2: Datei zu Staged URL hochladen
            upload_result = self._upload_to_staged_url(staged_target, image_data, filename)
            if not upload_result['success']:
                return False, upload_result['error'], ''

            # Schritt 3: File in Shopify erstellen
            file_result = self._create_file(resource_url, alt_text)
            if not file_result['success']:
                return False, file_result['error'], ''

            # Warte kurz und hole die finale URL
            cdn_url = file_result.get('url', '')
            file_id = file_result.get('file_id', '')

            if cdn_url:
                return True, cdn_url, file_id
            else:
                # Falls URL noch nicht verfügbar, Resource URL zurückgeben
                return True, resource_url, file_id

        except Exception as e:
            logger.error(f"Shopify Files Upload Fehler: {e}")
            return False, str(e), ''

    def _create_staged_upload(self, filename: str) -> Dict:
        """
        Erstellt einen Staged Upload in Shopify.

        Args:
            filename: Dateiname

        Returns:
            Dict mit success, staged_target und resource_url
        """
        mutation = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
            stagedUploadsCreate(input: $input) {
                stagedTargets {
                    url
                    resourceUrl
                    parameters {
                        name
                        value
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
            "input": [{
                "filename": f"{filename}.png",
                "mimeType": "image/png",
                "resource": "FILE",
                "httpMethod": "POST"
            }]
        }

        try:
            response = requests.post(
                self.graphql_url,
                json={"query": mutation, "variables": variables},
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                return {'success': False, 'error': f'GraphQL Fehler: {response.status_code}'}

            data = response.json()

            # Fehler prüfen
            if 'errors' in data:
                return {'success': False, 'error': str(data['errors'])}

            result = data.get('data', {}).get('stagedUploadsCreate', {})
            user_errors = result.get('userErrors', [])

            if user_errors:
                return {'success': False, 'error': str(user_errors)}

            staged_targets = result.get('stagedTargets', [])
            if not staged_targets:
                return {'success': False, 'error': 'Keine staged target erhalten'}

            target = staged_targets[0]
            return {
                'success': True,
                'staged_target': {
                    'url': target['url'],
                    'parameters': {p['name']: p['value'] for p in target['parameters']}
                },
                'resource_url': target['resourceUrl']
            }

        except requests.RequestException as e:
            return {'success': False, 'error': f'Request Fehler: {e}'}

    def _upload_to_staged_url(self, staged_target: Dict, image_data: str, filename: str) -> Dict:
        """
        Lädt die Datei zur Staged URL hoch.

        Args:
            staged_target: Dict mit url und parameters
            image_data: Base64-kodierte Bilddaten
            filename: Dateiname

        Returns:
            Dict mit success und ggf. error
        """
        try:
            # Base64 dekodieren
            image_bytes = base64.b64decode(image_data)

            # Multipart Form Data erstellen
            url = staged_target['url']
            params = staged_target['parameters']

            # Form fields hinzufügen
            files = {}
            for key, value in params.items():
                files[key] = (None, value)

            # Datei hinzufügen (muss als letztes kommen)
            files['file'] = (f"{filename}.png", image_bytes, 'image/png')

            response = requests.post(url, files=files, timeout=60)

            # Shopify Staged Upload gibt 201 oder 204 zurück
            if response.status_code in [200, 201, 204]:
                return {'success': True}
            else:
                return {'success': False, 'error': f'Upload Fehler: {response.status_code} - {response.text}'}

        except Exception as e:
            return {'success': False, 'error': f'Upload Fehler: {e}'}

    def _create_file(self, resource_url: str, alt_text: str = '') -> Dict:
        """
        Erstellt die Datei in Shopify Files.

        Args:
            resource_url: Resource URL vom Staged Upload
            alt_text: Alt-Text für das Bild

        Returns:
            Dict mit success, url und file_id
        """
        mutation = """
        mutation fileCreate($files: [FileCreateInput!]!) {
            fileCreate(files: $files) {
                files {
                    id
                    alt
                    createdAt
                    ... on MediaImage {
                        image {
                            url
                            originalSrc
                        }
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
            "files": [{
                "alt": alt_text,
                "contentType": "IMAGE",
                "originalSource": resource_url
            }]
        }

        try:
            response = requests.post(
                self.graphql_url,
                json={"query": mutation, "variables": variables},
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                return {'success': False, 'error': f'GraphQL Fehler: {response.status_code}'}

            data = response.json()

            if 'errors' in data:
                return {'success': False, 'error': str(data['errors'])}

            result = data.get('data', {}).get('fileCreate', {})
            user_errors = result.get('userErrors', [])

            if user_errors:
                return {'success': False, 'error': str(user_errors)}

            files = result.get('files', [])
            if not files:
                return {'success': False, 'error': 'Keine Datei erstellt'}

            file_obj = files[0]
            if not file_obj:
                return {'success': False, 'error': 'Datei-Objekt ist None'}

            file_id = file_obj.get('id', '') if file_obj else ''

            # URL aus MediaImage extrahieren - mit Null-Check
            image_data = file_obj.get('image') if file_obj else None
            if image_data:
                url = image_data.get('url') or image_data.get('originalSrc', '')
            else:
                # Fallback: Versuche resource_url zu verwenden
                url = ''
                logger.warning(f"Shopify file created but no image URL yet (file_id: {file_id})")

            return {
                'success': True,
                'file_id': file_id,
                'url': url
            }

        except requests.RequestException as e:
            return {'success': False, 'error': f'Request Fehler: {e}'}

    def upload_images_batch(self, images: list) -> Dict:
        """
        Lädt mehrere Bilder zu Shopify hoch.

        Args:
            images: Liste von Dicts mit {image_data, filename, alt_text}

        Returns:
            Dict mit success, uploaded (Liste von URLs) und errors
        """
        uploaded = []
        errors = []

        for img in images:
            success, result, file_id = self.upload_image_from_base64(
                img['image_data'],
                img['filename'],
                img.get('alt_text', '')
            )

            if success:
                uploaded.append({
                    'filename': img['filename'],
                    'url': result,
                    'file_id': file_id
                })
            else:
                errors.append({
                    'filename': img['filename'],
                    'error': result
                })

        return {
            'success': len(errors) == 0,
            'uploaded': uploaded,
            'errors': errors
        }

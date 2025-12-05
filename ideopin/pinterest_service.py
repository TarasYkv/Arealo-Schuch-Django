"""
Pinterest API Service für IdeoPin

Dieser Service ermöglicht:
- OAuth2-Authentifizierung mit Pinterest
- Abrufen der Boards eines Users
- Posten von Pins auf Pinterest
- Token-Refresh-Mechanismus
"""

import logging
import requests
import base64
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class PinterestAPIService:
    """Service-Klasse für Pinterest API v5 Integration"""

    # Pinterest API Endpoints
    BASE_URL = 'https://api.pinterest.com/v5'
    AUTH_URL = 'https://www.pinterest.com/oauth/'
    TOKEN_URL = 'https://api.pinterest.com/v5/oauth/token'

    # Standard Scopes für Pin-Posting
    DEFAULT_SCOPES = [
        'boards:read',
        'boards:write',
        'pins:read',
        'pins:write',
        'user_accounts:read',
    ]

    def __init__(self, pinterest_settings):
        """
        Initialisiert den Pinterest API Service.

        Args:
            pinterest_settings: PinterestAPISettings Model-Instanz
        """
        self.settings = pinterest_settings
        self.access_token = pinterest_settings.access_token if pinterest_settings else None

    def get_authorization_url(self, redirect_uri, state=None):
        """
        Generiert die Pinterest OAuth2 Autorisierungs-URL.

        Args:
            redirect_uri: Die Callback-URL nach der Autorisierung
            state: Optionaler State-Parameter für CSRF-Schutz

        Returns:
            Die vollständige Autorisierungs-URL
        """
        if not self.settings or not self.settings.app_id:
            raise ValueError("Pinterest App ID ist nicht konfiguriert")

        params = {
            'client_id': self.settings.app_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ','.join(self.DEFAULT_SCOPES),
        }

        if state:
            params['state'] = state

        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code, redirect_uri):
        """
        Tauscht den Authorization Code gegen Access und Refresh Tokens.

        Args:
            code: Der Authorization Code von Pinterest
            redirect_uri: Die gleiche Redirect URI wie bei der Autorisierung

        Returns:
            dict mit access_token, refresh_token, expires_in, scope
        """
        if not self.settings or not self.settings.app_id or not self.settings.app_secret:
            raise ValueError("Pinterest App Credentials sind nicht konfiguriert")

        # Basic Auth Header erstellen
        credentials = f"{self.settings.app_id}:{self.settings.app_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }

        try:
            response = requests.post(
                self.TOKEN_URL,
                headers=headers,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                logger.info(f"[Pinterest] Token exchange erfolgreich, Scopes: {token_data.get('scope')}")
                return {
                    'success': True,
                    'access_token': token_data.get('access_token'),
                    'refresh_token': token_data.get('refresh_token'),
                    'expires_in': token_data.get('expires_in', 2592000),  # 30 Tage default
                    'scope': token_data.get('scope', ''),
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                logger.error(f"[Pinterest] Token exchange fehlgeschlagen: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"[Pinterest] Token exchange Netzwerkfehler: {e}")
            return {
                'success': False,
                'error': f'Netzwerkfehler: {str(e)}',
            }

    def refresh_access_token(self):
        """
        Erneuert das Access Token mit dem Refresh Token.

        Returns:
            dict mit neuem access_token und expires_in
        """
        if not self.settings or not self.settings.refresh_token:
            return {'success': False, 'error': 'Kein Refresh Token verfügbar'}

        # Basic Auth Header erstellen
        credentials = f"{self.settings.app_id}:{self.settings.app_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.settings.refresh_token,
        }

        try:
            response = requests.post(
                self.TOKEN_URL,
                headers=headers,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                logger.info("[Pinterest] Token refresh erfolgreich")

                # Token in den Settings speichern
                self.settings.access_token = token_data.get('access_token')
                if token_data.get('refresh_token'):
                    self.settings.refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 2592000)
                self.settings.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                self.settings.save()

                self.access_token = self.settings.access_token

                return {
                    'success': True,
                    'access_token': token_data.get('access_token'),
                    'expires_in': expires_in,
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                logger.error(f"[Pinterest] Token refresh fehlgeschlagen: {error_msg}")

                # Bei Fehler Token als ungültig markieren
                self.settings.is_connected = False
                self.settings.last_error = error_msg
                self.settings.save()

                return {
                    'success': False,
                    'error': error_msg,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"[Pinterest] Token refresh Netzwerkfehler: {e}")
            return {
                'success': False,
                'error': f'Netzwerkfehler: {str(e)}',
            }

    def _ensure_valid_token(self):
        """Stellt sicher, dass ein gültiges Token vorhanden ist."""
        if not self.settings:
            return False

        if self.settings.needs_refresh():
            result = self.refresh_access_token()
            return result.get('success', False)

        return bool(self.access_token)

    def _make_request(self, method, endpoint, **kwargs):
        """
        Führt einen authentifizierten API-Request aus.

        Args:
            method: HTTP-Methode (GET, POST, etc.)
            endpoint: API-Endpoint (ohne Basis-URL)
            **kwargs: Weitere Argumente für requests

        Returns:
            Response-Objekt oder None bei Fehler
        """
        if not self._ensure_valid_token():
            return None

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=kwargs.pop('timeout', 60),
                **kwargs
            )
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"[Pinterest] API-Request fehlgeschlagen: {e}")
            return None

    def get_user_info(self):
        """
        Ruft die Benutzerinformationen ab.

        Returns:
            dict mit Benutzerinformationen oder Fehler
        """
        response = self._make_request('GET', '/user_account')

        if response and response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'username': data.get('username'),
                'profile_image': data.get('profile_image'),
                'account_type': data.get('account_type'),
            }
        elif response:
            error_data = response.json() if response.text else {}
            return {
                'success': False,
                'error': error_data.get('message', 'Unbekannter Fehler'),
            }
        else:
            return {
                'success': False,
                'error': 'Keine Verbindung zur Pinterest API',
            }

    def get_boards(self):
        """
        Ruft alle Boards des Benutzers ab.

        Returns:
            dict mit Liste der Boards oder Fehler
        """
        response = self._make_request('GET', '/boards', params={'page_size': 100})

        if response and response.status_code == 200:
            data = response.json()
            boards = []
            for board in data.get('items', []):
                boards.append({
                    'id': board.get('id'),
                    'name': board.get('name'),
                    'description': board.get('description', ''),
                    'privacy': board.get('privacy'),
                    'pin_count': board.get('pin_count', 0),
                })
            logger.info(f"[Pinterest] {len(boards)} Boards geladen")
            return {
                'success': True,
                'boards': boards,
            }
        elif response:
            error_data = response.json() if response.text else {}
            return {
                'success': False,
                'error': error_data.get('message', 'Fehler beim Laden der Boards'),
            }
        else:
            return {
                'success': False,
                'error': 'Keine Verbindung zur Pinterest API',
            }

    def create_pin(self, board_id, title, description, link, image_file=None, image_url=None):
        """
        Erstellt einen neuen Pin auf Pinterest.

        Args:
            board_id: ID des Ziel-Boards
            title: Pin-Titel (max 100 Zeichen)
            description: Pin-Beschreibung (max 500 Zeichen)
            link: Ziel-URL des Pins
            image_file: Bilddatei-Objekt (optional, wenn image_url nicht verwendet wird)
            image_url: URL zu einem öffentlich zugänglichen Bild (optional)

        Returns:
            dict mit Pin-ID und URL oder Fehler
        """
        if not image_file and not image_url:
            return {
                'success': False,
                'error': 'Entweder image_file oder image_url muss angegeben werden',
            }

        # Pin-Daten vorbereiten
        pin_data = {
            'board_id': board_id,
            'title': title[:100] if title else '',  # Max 100 Zeichen
            'description': description[:500] if description else '',  # Max 500 Zeichen
            'link': link or '',
        }

        # Bild als Base64 hochladen
        if image_file:
            try:
                # Bild lesen und als Base64 kodieren
                image_file.seek(0)
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # Media Source definieren
                pin_data['media_source'] = {
                    'source_type': 'image_base64',
                    'content_type': 'image/png',
                    'data': image_base64,
                }
            except Exception as e:
                logger.error(f"[Pinterest] Fehler beim Lesen des Bildes: {e}")
                return {
                    'success': False,
                    'error': f'Fehler beim Lesen des Bildes: {str(e)}',
                }
        else:
            # Externe Bild-URL verwenden
            pin_data['media_source'] = {
                'source_type': 'image_url',
                'url': image_url,
            }

        # API-Request senden
        response = self._make_request(
            'POST',
            '/pins',
            json=pin_data,
            headers={'Content-Type': 'application/json'},
        )

        if response and response.status_code in [200, 201]:
            data = response.json()
            pin_id = data.get('id')
            logger.info(f"[Pinterest] Pin erfolgreich erstellt: {pin_id}")
            return {
                'success': True,
                'pin_id': pin_id,
                'pin_url': f"https://www.pinterest.com/pin/{pin_id}/",
            }
        elif response:
            try:
                error_data = response.json()
            except Exception:
                error_data = {'message': response.text or 'Unbekannter Fehler'}

            error_msg = error_data.get('message', str(error_data))
            logger.error(f"[Pinterest] Pin-Erstellung fehlgeschlagen: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
            }
        else:
            return {
                'success': False,
                'error': 'Keine Verbindung zur Pinterest API',
            }

    def post_pin_from_project(self, project, board_id):
        """
        Postet einen Pin aus einem PinProject auf Pinterest.

        Args:
            project: PinProject Model-Instanz
            board_id: ID des Ziel-Boards

        Returns:
            dict mit Erfolg/Fehler und Pin-Details
        """
        # Bild auswählen
        image_file = project.get_final_image_for_upload()
        if not image_file:
            return {
                'success': False,
                'error': 'Kein Bild vorhanden. Bitte zuerst ein Bild generieren.',
            }

        # Pin-Titel aus Overlay-Text oder Keywords ableiten
        title = project.overlay_text or project.keywords[:100]

        # Pin erstellen
        try:
            with image_file.open('rb') as f:
                result = self.create_pin(
                    board_id=board_id,
                    title=title,
                    description=project.seo_description or '',
                    link=project.pin_url or '',
                    image_file=f,
                )
        except Exception as e:
            logger.error(f"[Pinterest] Fehler beim Öffnen des Bildes: {e}")
            return {
                'success': False,
                'error': f'Fehler beim Öffnen des Bildes: {str(e)}',
            }

        # Projekt aktualisieren
        if result.get('success'):
            project.pinterest_posted = True
            project.pinterest_pin_id = result.get('pin_id', '')
            project.pinterest_board_id = board_id
            project.pinterest_posted_at = timezone.now()
            project.pinterest_post_error = ''
            project.save()
            logger.info(f"[Pinterest] Projekt {project.id} erfolgreich gepostet")
        else:
            project.pinterest_post_error = result.get('error', 'Unbekannter Fehler')
            project.save()

        return result

    def test_connection(self):
        """
        Testet die Pinterest-Verbindung.

        Returns:
            dict mit Erfolg/Fehler und Benutzerinformationen
        """
        user_info = self.get_user_info()

        if user_info.get('success'):
            # Verbindung erfolgreich, Settings aktualisieren
            self.settings.is_connected = True
            self.settings.pinterest_username = user_info.get('username', '')
            self.settings.last_test_success = timezone.now()
            self.settings.last_error = ''
            self.settings.save()

            return {
                'success': True,
                'username': user_info.get('username'),
                'message': f"Verbunden als @{user_info.get('username')}",
            }
        else:
            self.settings.is_connected = False
            self.settings.last_error = user_info.get('error', 'Unbekannter Fehler')
            self.settings.save()

            return {
                'success': False,
                'error': user_info.get('error'),
            }

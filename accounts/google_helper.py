"""Zentraler Google-OAuth-Helper für alle Workloom-Skills.

Pro User wird der OAuth-Token EINMAL angefragt und in CustomUser.google_oauth_credentials
verschlüsselt gespeichert. Skills holen sich darüber Drive/Gmail/Calendar/Sheets-Services.

Alle Scopes werden BEIM CONNECT angefragt — Skills müssen nicht erneut OAuth-Flow starten.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


# Alle Scopes die Workloom-Skills jemals brauchen — werden EINMAL beim Connect angefragt.
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.file',          # Lasergravur (PNG-Upload)
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/gmail.send',          # Email-Versand
    'https://www.googleapis.com/auth/calendar',            # Calendar
    'https://www.googleapis.com/auth/spreadsheets',        # Sheets
    'https://www.googleapis.com/auth/userinfo.email',      # Email-Adresse für Anzeige
    'openid',
]


def get_oauth_flow(redirect_uri: str = None):
    """Liefert google_auth_oauthlib.Flow mit Workloom-Client-Config."""
    from google_auth_oauthlib.flow import Flow
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        raise RuntimeError(
            'GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET fehlen in Settings/.env'
        )
    if not redirect_uri:
        redirect_uri = getattr(
            settings, 'GOOGLE_OAUTH_REDIRECT_URI',
            'https://workloom.de/accounts/google/callback/',
        )
    flow = Flow.from_client_config(
        {
            'web': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [redirect_uri],
            }
        },
        scopes=GOOGLE_SCOPES,
    )
    flow.redirect_uri = redirect_uri
    return flow


def credentials_to_dict(credentials) -> dict:
    """Serialisiert google.oauth2.credentials.Credentials für DB-Speicherung."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
    }


def credentials_from_user(user):
    """Lädt google.oauth2.credentials.Credentials aus User-Profil.

    Bei Token-Ablauf wird automatisch refreshed + neu gespeichert.
    Liefert None wenn User keinen Google-Account verbunden hat.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    raw = getattr(user, 'google_oauth_credentials', '') or ''
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception as exc:
        logger.warning('google_oauth_credentials für %s nicht parsbar: %s', user, exc)
        return None

    expiry = None
    if data.get('expiry'):
        from datetime import datetime
        try:
            expiry = datetime.fromisoformat(data['expiry'])
        except Exception:
            pass

    creds = Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri=data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes', GOOGLE_SCOPES),
    )
    if expiry:
        creds.expiry = expiry

    # Auto-Refresh bei Ablauf
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Aktualisierten Token zurückspeichern
            user.google_oauth_credentials = json.dumps(credentials_to_dict(creds))
            user.save(update_fields=['google_oauth_credentials'])
            logger.info('Google-Token für %s automatisch erneuert', user)
        except Exception as exc:
            logger.warning('Google-Token-Refresh für %s fehlgeschlagen: %s', user, exc)
            return None
    return creds


# ---------------------------------------------------------- Service-Factory

def get_drive_service(user):
    """Liefert authentifizierten Drive-API-Service für den User."""
    from googleapiclient.discovery import build
    creds = credentials_from_user(user)
    if not creds:
        raise RuntimeError(
            f'User {user} hat keinen Google-Account verbunden — '
            f'bitte unter /accounts/api-einstellungen/ verbinden.'
        )
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def get_gmail_service(user):
    """Liefert authentifizierten Gmail-API-Service für den User."""
    from googleapiclient.discovery import build
    creds = credentials_from_user(user)
    if not creds:
        raise RuntimeError(f'User {user} hat keinen Google-Account verbunden.')
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def get_calendar_service(user):
    from googleapiclient.discovery import build
    creds = credentials_from_user(user)
    if not creds:
        raise RuntimeError(f'User {user} hat keinen Google-Account verbunden.')
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def get_sheets_service(user):
    from googleapiclient.discovery import build
    creds = credentials_from_user(user)
    if not creds:
        raise RuntimeError(f'User {user} hat keinen Google-Account verbunden.')
    return build('sheets', 'v4', credentials=creds, cache_discovery=False)


def fetch_user_email(credentials) -> str:
    """Liest die Email-Adresse des verbundenen Google-Accounts.

    Wird beim Connect aufgerufen um google_account_email zu setzen.
    """
    from googleapiclient.discovery import build
    try:
        oauth2 = build('oauth2', 'v2', credentials=credentials, cache_discovery=False)
        info = oauth2.userinfo().get().execute()
        return info.get('email', '')
    except Exception as exc:
        logger.warning('Konnte Google-Userinfo nicht abrufen: %s', exc)
        return ''

import requests
from typing import Dict, Optional, Any
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CentralAPIClient:
    """
    Client für die zentrale API-Key-Verwaltung
    Holt API-Keys von der zentralen Stelle /accounts/neue-api-einstellungen/
    """
    
    def __init__(self, user: User):
        self.user = user
        self._cache_timeout = 3600  # 1 Stunde Cache für API-Keys
    
    def get_api_keys(self) -> Dict[str, Optional[str]]:
        """
        Holt alle API-Keys für den Benutzer von der zentralen Stelle
        
        Returns:
            Dict mit den API-Keys:
            {
                'openai': 'key...',
                'anthropic': 'key...',
                'google': 'key...',
                'youtube': 'key...'
            }
        """
        # Cache-Key für diesen Benutzer
        cache_key = f'api_keys_user_{self.user.id}'
        
        # Versuche aus Cache zu laden
        cached_keys = cache.get(cache_key)
        if cached_keys:
            logger.debug(f"API-Keys für User {self.user.username} aus Cache geladen")
            return cached_keys
        
        # Direkt aus dem User-Model laden (da die Keys dort gespeichert sind)
        api_keys = {
            'openai': self.user.openai_api_key,
            'anthropic': self.user.anthropic_api_key,
            'google': self.user.google_api_key,
            'youtube': self.user.youtube_api_key
        }
        
        # In Cache speichern
        cache.set(cache_key, api_keys, self._cache_timeout)
        logger.debug(f"API-Keys für User {self.user.username} in Cache gespeichert")
        
        return api_keys
    
    def get_openai_key(self) -> Optional[str]:
        """Holt nur den OpenAI API-Key"""
        keys = self.get_api_keys()
        return keys.get('openai')
    
    def get_anthropic_key(self) -> Optional[str]:
        """Holt nur den Anthropic API-Key"""
        keys = self.get_api_keys()
        return keys.get('anthropic')
    
    def get_google_key(self) -> Optional[str]:
        """Holt nur den Google API-Key"""
        keys = self.get_api_keys()
        return keys.get('google')
    
    def get_youtube_key(self) -> Optional[str]:
        """Holt nur den YouTube API-Key"""
        keys = self.get_api_keys()
        return keys.get('youtube')
    
    def clear_cache(self):
        """Löscht den Cache für diesen Benutzer"""
        cache_key = f'api_keys_user_{self.user.id}'
        cache.delete(cache_key)
        logger.debug(f"Cache für User {self.user.username} gelöscht")
    
    def validate_api_keys(self) -> Dict[str, bool]:
        """
        Validiert die vorhandenen API-Keys
        
        Returns:
            Dict mit Validierungsstatus:
            {
                'openai': True/False,
                'anthropic': True/False,
                'google': True/False,
                'youtube': True/False
            }
        """
        keys = self.get_api_keys()
        validation = {}
        
        for service, key in keys.items():
            validation[service] = bool(key and key.strip())
        
        return validation
    
    def has_required_keys(self, required_services: list) -> bool:
        """
        Prüft ob alle erforderlichen API-Keys vorhanden sind
        
        Args:
            required_services: Liste der erforderlichen Services
                             z.B. ['openai', 'google']
        
        Returns:
            True wenn alle erforderlichen Keys vorhanden sind
        """
        validation = self.validate_api_keys()
        
        for service in required_services:
            if not validation.get(service, False):
                logger.warning(f"Fehlender API-Key für Service: {service}")
                return False
        
        return True
    
    def get_service_url(self) -> str:
        """
        Gibt die URL zur API-Einstellungsseite zurück
        """
        return '/accounts/neue-api-einstellungen/'
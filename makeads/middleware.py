from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from .api_client import CentralAPIClient
import logging

logger = logging.getLogger(__name__)


class APIKeyCacheMiddleware(MiddlewareMixin):
    """
    Middleware die den API-Key Cache bei Änderungen invalidiert
    """
    
    def process_request(self, request):
        # Prüfe ob wir auf der API-Einstellungsseite sind
        if request.path == '/accounts/neue-api-einstellungen/' and request.method == 'POST':
            # Markiere für Cache-Invalidierung nach erfolgreicher Änderung
            request._should_clear_api_cache = True
        return None
    
    def process_response(self, request, response):
        # Wenn API-Keys geändert wurden und die Anfrage erfolgreich war
        if hasattr(request, '_should_clear_api_cache') and response.status_code in [200, 302]:
            if request.user.is_authenticated:
                # Cache für diesen Benutzer löschen
                api_client = CentralAPIClient(request.user)
                api_client.clear_cache()
                logger.info(f"API-Key Cache für User {request.user.username} gelöscht")
        
        return response
from django.contrib import messages
from .api_client import CentralAPIClient


def check_api_key_configuration(request, required_services=None):
    """
    Hilfsfunktion um API-Key Konfiguration zu prüfen und Nachrichten anzuzeigen
    
    Args:
        request: Django request object
        required_services: Liste der erforderlichen Services
        
    Returns:
        bool: True wenn alle erforderlichen Keys vorhanden sind
    """
    if not request.user.is_authenticated:
        return False
    
    api_client = CentralAPIClient(request.user)
    
    # Standard: OpenAI ist erforderlich
    if required_services is None:
        required_services = ['openai']
    
    # Validierung durchführen
    validation = api_client.validate_api_keys()
    missing_services = []
    
    for service in required_services:
        if not validation.get(service, False):
            missing_services.append(service)
    
    if missing_services:
        # Service-Namen für Anzeige
        service_names = {
            'openai': 'OpenAI',
            'anthropic': 'Anthropic',
            'google': 'Google AI',
            'youtube': 'YouTube'
        }
        
        missing_names = [service_names.get(s, s) for s in missing_services]
        
        messages.warning(
            request,
            f'Bitte konfigurieren Sie folgende API-Keys für MakeAds: {", ".join(missing_names)}. '
            f'<a href="{api_client.get_service_url()}" class="text-primary">Jetzt konfigurieren</a>',
            extra_tags='safe'  # Erlaubt HTML in der Nachricht
        )
        
        return False
    
    return True


def get_available_ai_services(user):
    """
    Gibt die verfügbaren AI-Services für einen Benutzer zurück
    
    Args:
        user: Django User object
        
    Returns:
        list: Liste der verfügbaren Service-Namen
    """
    api_client = CentralAPIClient(user)
    validation = api_client.validate_api_keys()
    
    available = []
    
    if validation.get('openai'):
        available.append('openai')
    
    if validation.get('anthropic'):
        available.append('claude')
    
    if validation.get('google'):
        available.append('google')
    
    return available
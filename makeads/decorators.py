from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .api_client import CentralAPIClient


def require_api_keys(required_services=['openai']):
    """
    Decorator der prüft ob die erforderlichen API-Keys vorhanden sind
    
    Args:
        required_services: Liste der erforderlichen Services
                         Standard: ['openai']
    
    Usage:
        @require_api_keys(['openai', 'google'])
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # API-Client initialisieren
            api_client = CentralAPIClient(request.user)
            
            # Prüfe ob alle erforderlichen Keys vorhanden sind
            if not api_client.has_required_keys(required_services):
                # Fehlende Services ermitteln
                validation = api_client.validate_api_keys()
                missing_services = []
                
                for service in required_services:
                    if not validation.get(service, False):
                        missing_services.append(service)
                
                # Fehlermeldung erstellen
                service_names = {
                    'openai': 'OpenAI',
                    'anthropic': 'Anthropic',
                    'google': 'Google AI',
                    'youtube': 'YouTube'
                }
                
                missing_names = [service_names.get(s, s) for s in missing_services]
                
                messages.error(
                    request,
                    f'Bitte konfigurieren Sie folgende API-Keys: {", ".join(missing_names)}. '
                    f'<a href="{api_client.get_service_url()}" class="text-primary">Zu den API-Einstellungen</a>'
                )
                
                # Zur Dashboard oder API-Einstellungen weiterleiten
                return redirect('makeads:dashboard')
            
            # View ausführen wenn alle Keys vorhanden sind
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator


def optional_api_keys(services=['openai', 'anthropic', 'google']):
    """
    Decorator der API-Keys als optional markiert aber Warnungen anzeigt
    
    Args:
        services: Liste der optionalen Services
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # API-Client initialisieren
            api_client = CentralAPIClient(request.user)
            
            # Prüfe welche Keys fehlen
            validation = api_client.validate_api_keys()
            missing_services = []
            
            for service in services:
                if not validation.get(service, False):
                    missing_services.append(service)
            
            # Warnung anzeigen wenn Keys fehlen
            if missing_services:
                service_names = {
                    'openai': 'OpenAI',
                    'anthropic': 'Anthropic',
                    'google': 'Google AI',
                    'youtube': 'YouTube'
                }
                
                missing_names = [service_names.get(s, s) for s in missing_services]
                
                messages.warning(
                    request,
                    f'Für erweiterte Funktionen konfigurieren Sie bitte: {", ".join(missing_names)}. '
                    f'<a href="{api_client.get_service_url()}" class="text-info">API-Keys konfigurieren</a>'
                )
            
            # View trotzdem ausführen
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator
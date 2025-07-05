import os
from django.conf import settings
from accounts.models import CustomUser # Import CustomUser


def get_user_api_key(user: CustomUser, provider: str):
    """
    Holt den API-Key für einen User und Provider.
    Priorisiert Keys aus dem CustomUser-Modell, fällt auf .env-Keys zurück.
    
    Args:
        user: CustomUser object
        provider: str - 'openai', 'anthropic', oder 'google'
    
    Returns:
        str: API-Key oder None falls nicht verfügbar
    """
    if not user or not user.is_authenticated:
        # Fallback für nicht authentifizierte Requests oder wenn kein User-Objekt vorhanden ist
        return get_env_api_key(provider)
    
    # 1. Versuche Key aus CustomUser-Modell zu holen
    if provider == 'openai':
        if user.openai_api_key and user.openai_api_key.strip():
            return user.openai_api_key.strip()
    elif provider == 'anthropic':
        if user.anthropic_api_key and user.anthropic_api_key.strip():
            return user.anthropic_api_key.strip()
    
    # 2. Fallback zu .env-Key (für Google und andere, die nicht im User-Modell sind)
    return get_env_api_key(provider)


def get_env_api_key(provider):
    """
    Holt API-Key aus Environment-Variablen (.env-Datei).
    
    Args:
        provider: str - 'openai', 'anthropic', 'google', oder 'youtube'
    
    Returns:
        str: API-Key oder None falls nicht verfügbar
    """
    env_key_mapping = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'google': 'GOOGLE_AI_API_KEY',
        'youtube': 'YOUTUBE_API_KEY'
    }
    
    env_key = env_key_mapping.get(provider)
    if not env_key:
        return None
    
    # Versuche aus Django settings
    api_key = getattr(settings, env_key, None)
    if api_key:
        return api_key
    
    # Fallback zu os.getenv
    return os.getenv(env_key)


def get_provider_from_model(model_name):
    """
    Ermittelt den Provider basierend auf dem Model-Namen.
    
    Args:
        model_name: str - Name des AI-Models
    
    Returns:
        str: Provider-Name ('openai', 'anthropic', 'google')
    """
    model_name_lower = model_name.lower()
    
    if any(keyword in model_name_lower for keyword in ['gpt', 'chatgpt', 'openai', 'o1', 'o3']):
        return 'openai'
    elif any(keyword in model_name_lower for keyword in ['claude', 'anthropic', 'sonnet', 'opus', 'haiku']):
        return 'anthropic'
    elif any(keyword in model_name_lower for keyword in ['gemini', 'google', 'bard']):
        return 'google'
    else:
        # Default fallback
        return 'openai'


def has_user_api_key(user, provider):
    """
    Prüft ob ein User einen API-Key für einen Provider hat.
    
    Args:
        user: Django User object
        provider: str - Provider-Name
    
    Returns:
        bool: True wenn Key verfügbar, False sonst
    """
    api_key = get_user_api_key(user, provider)
    return bool(api_key and api_key.strip())
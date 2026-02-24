"""
Clawboard AI Chat Service - Multi-Provider Support
"""
import logging
from typing import Optional, List, Dict

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Verfuegbare Modelle pro Provider
AVAILABLE_MODELS = {
    'openai': [
        {'id': 'gpt-4o', 'name': 'GPT-4o', 'description': 'Leistungsstark & schnell'},
        {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'description': 'Guenstig & schnell'},
        {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'description': 'Stark & vielseitig'},
    ],
    'anthropic': [
        {'id': 'claude-sonnet-4-20250514', 'name': 'Claude Sonnet 4', 'description': 'Stark & schnell'},
        {'id': 'claude-3-5-sonnet-20241022', 'name': 'Claude 3.5 Sonnet', 'description': 'Premium'},
        {'id': 'claude-3-5-haiku-20241022', 'name': 'Claude 3.5 Haiku', 'description': 'Schnell & guenstig'},
    ],
    'gemini': [
        {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash', 'description': 'Schnell'},
        {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'description': 'Leistungsstark'},
        {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash', 'description': 'Guenstig & schnell'},
    ],
}


def get_available_models_for_user(user):
    """Gibt verfuegbare Modelle basierend auf den API-Keys des Users zurueck."""
    models = []

    if getattr(user, 'openai_api_key', None) and OPENAI_AVAILABLE:
        for m in AVAILABLE_MODELS['openai']:
            models.append({**m, 'provider': 'openai', 'icon': 'bi-stars'})

    if getattr(user, 'anthropic_api_key', None) and ANTHROPIC_AVAILABLE:
        for m in AVAILABLE_MODELS['anthropic']:
            models.append({**m, 'provider': 'anthropic', 'icon': 'bi-robot'})

    if (getattr(user, 'gemini_api_key', None) or getattr(user, 'google_api_key', None)) and GEMINI_AVAILABLE:
        for m in AVAILABLE_MODELS['gemini']:
            models.append({**m, 'provider': 'gemini', 'icon': 'bi-google'})

    return models


def call_ai_chat(user, provider: str, model: str, messages: List[Dict]) -> Optional[str]:
    """Ruft die KI-API auf und gibt die Antwort zurueck."""
    if provider == 'openai':
        return _call_openai(user, model, messages)
    elif provider == 'anthropic':
        return _call_anthropic(user, model, messages)
    elif provider == 'gemini':
        return _call_gemini(user, model, messages)
    else:
        raise ValueError(f"Unbekannter Provider: {provider}")


def _call_openai(user, model: str, messages: List[Dict]) -> Optional[str]:
    if not OPENAI_AVAILABLE:
        raise ImportError("OpenAI Paket nicht installiert")

    api_key = user.openai_api_key
    if not api_key:
        raise ValueError("OpenAI API-Key nicht konfiguriert")

    client = openai.OpenAI(api_key=api_key)
    # Nur role + content fuer die API
    api_messages = [{'role': m['role'], 'content': m['content']} for m in messages]

    response = client.chat.completions.create(
        model=model,
        messages=api_messages,
        temperature=0.7,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _call_anthropic(user, model: str, messages: List[Dict]) -> Optional[str]:
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("Anthropic Paket nicht installiert")

    api_key = user.anthropic_api_key
    if not api_key:
        raise ValueError("Anthropic API-Key nicht konfiguriert")

    client = anthropic.Anthropic(api_key=api_key)

    # System-Message extrahieren
    system_message = ""
    user_messages = []
    for msg in messages:
        if msg['role'] == 'system':
            system_message = msg['content']
        else:
            user_messages.append({'role': msg['role'], 'content': msg['content']})

    kwargs = {
        'model': model,
        'max_tokens': 4096,
        'messages': user_messages,
    }
    if system_message:
        kwargs['system'] = system_message

    response = client.messages.create(**kwargs)
    return response.content[0].text


def _call_gemini(user, model: str, messages: List[Dict]) -> Optional[str]:
    if not GEMINI_AVAILABLE:
        raise ImportError("Google Generative AI Paket nicht installiert")

    api_key = user.gemini_api_key or user.google_api_key
    if not api_key:
        raise ValueError("Gemini API-Key nicht konfiguriert")

    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model)

    # Messages in Gemini-Format konvertieren
    history = []
    last_content = None
    for msg in messages:
        if msg['role'] == 'system':
            # System als erster User-Turn
            history.append({'role': 'user', 'parts': [f"Anweisung: {msg['content']}"]})
            history.append({'role': 'model', 'parts': ['Verstanden.']})
        elif msg['role'] == 'user':
            history.append({'role': 'user', 'parts': [msg['content']]})
            last_content = msg['content']
        elif msg['role'] == 'assistant':
            history.append({'role': 'model', 'parts': [msg['content']]})

    if not history:
        return None

    # Letzte User-Nachricht als send_message, Rest als History
    if len(history) >= 2:
        chat = gemini_model.start_chat(history=history[:-1])
        response = chat.send_message(history[-1]['parts'][0])
    else:
        response = gemini_model.generate_content(history[0]['parts'][0])

    return response.text

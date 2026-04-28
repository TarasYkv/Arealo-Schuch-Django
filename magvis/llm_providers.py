"""Magvis Multi-Provider LLM-Konfiguration.

Definiert verfuegbare KI-Provider, deren Modelle und welche User-API-Key-
Felder sie nutzen. Wird in der Settings-UI fuer Provider/Modell-Dropdowns
verwendet UND vom MagvisLLMClient zur Auswahl des passenden Endpoints.
"""

# OpenAI-kompatibles Format = chat/completions mit messages[]
# Anthropic = eigenes /messages-Format
# Gemini = eigenes generateContent-Format

PROVIDERS = {
    'openai': {
        'label': 'OpenAI',
        'key_attr': 'openai_api_key',
        'base_url': 'https://api.openai.com/v1',
        'compat': 'openai',
        'models': [
            {'id': 'gpt-4o', 'label': 'GPT-4o (Top, ausgewogen)'},
            {'id': 'gpt-4o-mini', 'label': 'GPT-4o Mini (guenstig)'},
            {'id': 'gpt-4-turbo', 'label': 'GPT-4 Turbo'},
            {'id': 'gpt-3.5-turbo', 'label': 'GPT-3.5 Turbo (sehr guenstig)'},
        ],
    },
    'anthropic': {
        'label': 'Anthropic Claude',
        'key_attr': 'anthropic_api_key',
        'base_url': 'https://api.anthropic.com/v1',
        'compat': 'anthropic',
        'models': [
            {'id': 'claude-opus-4-7-20260301', 'label': 'Claude Opus 4.7 (Top, sehr teuer)'},
            {'id': 'claude-sonnet-4-6-20260101', 'label': 'Claude Sonnet 4.6 (empfohlen)'},
            {'id': 'claude-haiku-4-5-20251001', 'label': 'Claude Haiku 4.5 (schnell, guenstig)'},
        ],
    },
    'gemini': {
        'label': 'Google Gemini',
        'key_attr': 'gemini_api_key',
        'base_url': 'https://generativelanguage.googleapis.com/v1beta',
        'compat': 'gemini',
        'models': [
            {'id': 'gemini-2.5-flash', 'label': 'Gemini 2.5 Flash (schnell, guenstig)'},
            {'id': 'gemini-2.5-pro', 'label': 'Gemini 2.5 Pro'},
            {'id': 'gemini-3-pro', 'label': 'Gemini 3 Pro (Top)'},
            {'id': 'gemini-1.5-flash', 'label': 'Gemini 1.5 Flash (Legacy)'},
        ],
    },
    'zhipu': {
        'label': 'Z.AI / GLM',
        'key_attr': 'zhipu_api_key',
        'base_url': 'https://api.z.ai/api/coding/paas/v4',
        'compat': 'openai',
        'models': [
            {'id': 'glm-5.1', 'label': 'GLM-5.1 (Top, empfohlen)'},
            {'id': 'glm-4.6', 'label': 'GLM-4.6'},
            {'id': 'glm-4.5', 'label': 'GLM-4.5'},
            {'id': 'glm-4-air', 'label': 'GLM-4-Air (guenstig)'},
        ],
    },
    'deepseek': {
        'label': 'DeepSeek',
        'key_attr': 'deepseek_api_key',
        'base_url': 'https://api.deepseek.com/v1',
        'compat': 'openai',
        'models': [
            {'id': 'deepseek-chat', 'label': 'DeepSeek-V3 (Standard)'},
            {'id': 'deepseek-reasoner', 'label': 'DeepSeek-R1 (Reasoning)'},
        ],
    },
    'openrouter': {
        'label': 'OpenRouter (viele Modelle)',
        'key_attr': 'openrouter_api_key',
        'base_url': 'https://openrouter.ai/api/v1',
        'compat': 'openai',
        'models': [
            {'id': 'openai/gpt-4o', 'label': 'GPT-4o via OpenRouter'},
            {'id': 'anthropic/claude-3.5-sonnet', 'label': 'Claude 3.5 Sonnet via OR'},
            {'id': 'google/gemini-2.0-flash-exp:free', 'label': 'Gemini 2.0 (gratis)'},
            {'id': 'meta-llama/llama-3.3-70b-instruct', 'label': 'Llama 3.3 70B'},
            {'id': 'deepseek/deepseek-chat', 'label': 'DeepSeek via OR'},
            {'id': 'qwen/qwen-2.5-72b-instruct', 'label': 'Qwen 2.5 72B'},
        ],
    },
}


def provider_choices() -> list[tuple[str, str]]:
    """Choices fuer ChoiceField (alle Provider, unabhaengig von API-Key)."""
    return [(k, v['label']) for k, v in PROVIDERS.items()]


def available_providers_for(user) -> dict[str, dict]:
    """Liefert nur Provider, fuer die der User einen API-Key gesetzt hat."""
    out = {}
    for slug, cfg in PROVIDERS.items():
        key = getattr(user, cfg['key_attr'], None)
        if key:
            out[slug] = cfg
    return out


def models_for_provider(provider_slug: str) -> list[dict]:
    """Liste der verfuegbaren Modelle fuer einen Provider-Slug."""
    return PROVIDERS.get(provider_slug, {}).get('models', [])

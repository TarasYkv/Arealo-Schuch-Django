"""Council-Service: parallele Abfrage mehrerer KI-Modelle.

Adaptiert aus ~/clawd/council.py — hier aber Django-integriert mit
Key-Auflösung aus User-Profil + settings.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request

from django.conf import settings


# -- Modell-Definitionen (Provider + Endpoint + Modellname + Env-Key-Feld) -----

PROVIDERS: dict[str, dict] = {
    # key: provider-id (openrouter/openai/anthropic/gemini/zhipu/deepseek/nvidia)
    # url: Endpoint
    # api: 'openai' | 'anthropic' | 'gemini'
    'openrouter': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'api': 'openai',
        'env': 'OPENROUTER_API_KEY',
    },
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'api': 'openai',
        'env': 'OPENAI_API_KEY',
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/messages',
        'api': 'anthropic',
        'env': 'ANTHROPIC_API_KEY',
    },
    'gemini': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'api': 'gemini',
        'env': 'GOOGLE_AI_API_KEY',
    },
    'deepseek': {
        'url': 'https://api.deepseek.com/v1/chat/completions',
        'api': 'openai',
        'env': 'DEEPSEEK_API_KEY',
    },
    'zhipu': {
        'url': 'https://api.z.ai/api/coding/paas/v4/chat/completions',
        'api': 'openai',
        'env': 'ZHIPU_API_KEY',
    },
}


# Verfügbare Modelle:
#   id → {name, provider, model_id, pricing: (input_per_1M_usd, output_per_1M_usd), notes}
# Preise sind Richtwerte in USD pro 1 Mio. Tokens, Stand 2026-04. Schwanken je nach
# Anbieter/Route; Details: https://openrouter.ai/models, https://anthropic.com/pricing
MODELS = {
    'opus':     {'name': 'Claude Opus 4.7',       'provider': 'anthropic',  'model': 'claude-opus-4-7',
                 'pricing': (15.00, 75.00), 'context': '1M',
                 'notes': 'Stärkstes Modell, bester Schreibstil, Deutsch exzellent. Teuer.'},
    'sonnet':   {'name': 'Claude Sonnet 4.6',     'provider': 'anthropic',  'model': 'claude-sonnet-4-6',
                 'pricing': (3.00, 15.00), 'context': '200k',
                 'notes': 'Sehr guter Allrounder, deutlich günstiger als Opus.'},
    'haiku':    {'name': 'Claude Haiku 4.5',      'provider': 'anthropic',  'model': 'claude-haiku-4-5-20251001',
                 'pricing': (1.00, 5.00), 'context': '200k',
                 'notes': 'Schnell und günstig, für einfache Aufgaben.'},
    'gpt':      {'name': 'GPT-5.4',               'provider': 'openrouter', 'model': 'openai/gpt-5.4',
                 'pricing': (5.00, 15.00), 'context': '400k',
                 'notes': 'OpenAI, starkes Reasoning bei Mathe + Statistik.'},
    'gemini':   {'name': 'Gemini 3.1 Pro',        'provider': 'gemini',     'model': 'gemini-3.1-pro-preview',
                 'pricing': (1.25, 10.00), 'context': '2M',
                 'notes': 'Riesiges Kontextfenster, gut für lange Texte.'},
    'grok':     {'name': 'Grok 4.20',             'provider': 'openrouter', 'model': 'x-ai/grok-4.20',
                 'pricing': (3.00, 15.00), 'context': '256k',
                 'notes': 'xAI, gutes allgemeines Reasoning.'},
    'deepseek': {'name': 'DeepSeek Reasoner',     'provider': 'deepseek',   'model': 'deepseek-reasoner',
                 'pricing': (0.55, 2.19), 'context': '128k',
                 'notes': 'Sehr günstig, starkes Reasoning, chinesisches Modell.'},
    'glm':      {'name': 'GLM 5.1',               'provider': 'zhipu',      'model': 'glm-5.1',
                 'pricing': (0.20, 1.10), 'context': '128k',
                 'notes': 'Sehr günstig, sehr schnell, solide Qualität.'},
    'kimi':     {'name': 'Kimi K2',               'provider': 'openrouter', 'model': 'moonshotai/kimi-k2-instruct',
                 'pricing': (0.60, 2.50), 'context': '200k',
                 'notes': 'Moonshot AI, guter Allrounder.'},
    'qwen':     {'name': 'Qwen 3.6 Plus',         'provider': 'openrouter', 'model': 'qwen/qwen3.6-plus',
                 'pricing': (0.40, 1.20), 'context': '128k',
                 'notes': 'Alibaba, sehr stark multilingual.'},
    'mistral':  {'name': 'Mistral Large 3',       'provider': 'openrouter', 'model': 'mistralai/mistral-large-3-675b-instruct-2512',
                 'pricing': (2.00, 6.00), 'context': '128k',
                 'notes': 'Mistral, europäischer Anbieter, solide.'},
    'minimax':  {'name': 'MiniMax M2.7',          'provider': 'openrouter', 'model': 'minimax/minimax-m2.7',
                 'pricing': (0.50, 2.00), 'context': '128k',
                 'notes': 'MiniMax, schnell und günstig.'},
    'nemotron': {'name': 'NVIDIA Nemotron 120B',  'provider': 'openrouter', 'model': 'nvidia/nemotron-3-super-120b-a12b:free',
                 'pricing': (0.00, 0.00), 'context': '128k',
                 'notes': 'KOSTENLOS via OpenRouter (rate-limited).'},
    'mercury':  {'name': 'Mercury 2',             'provider': 'openrouter', 'model': 'inception/mercury-2',
                 'pricing': (0.50, 2.00), 'context': '32k',
                 'notes': 'Inception Mercury, sehr schnell.'},
}


def _as_tuple(cfg: dict) -> tuple:
    """Backward-compatibility: ältere Aufrufer erwarten (name, provider, model_id)."""
    return (cfg['name'], cfg['provider'], cfg['model'])


# Kompatibilitäts-Layer: alte Aufrufe wie MODELS['opus'][0] funktionieren weiter,
# indem wir das Dict via __getitem__ auch als Tuple zurückgeben können. Hier
# behalten wir das Dict-Format und passen alle Aufrufer an.


def display_name(model_id: str) -> str:
    m = MODELS.get(model_id)
    return m['name'] if m else model_id


# -- Key-Auflösung -------------------------------------------------------------

USER_KEY_FIELDS = {
    # Mapping: Provider-id → CustomUser-Feld
    'anthropic': 'anthropic_api_key',
    'openai': 'openai_api_key',
    'gemini': 'gemini_api_key',
    'openrouter': 'openrouter_api_key',
    'deepseek': 'deepseek_api_key',
    'zhipu': 'zhipu_api_key',
}


def _get_api_key(user, provider_id: str) -> str | None:
    """Key-Resolver: NUR User-Profil. Kein Env-Fallback — wir wollen, dass jeder
    User seinen eigenen Key einträgt (Kostenzuordnung, Kontingent, Nachvollziehbarkeit)."""
    candidates: list[str] = []
    if provider_id == 'gemini':
        candidates = ['gemini_api_key', 'google_api_key']
    else:
        field = USER_KEY_FIELDS.get(provider_id)
        if field:
            candidates = [field]
    for field in candidates:
        if user and getattr(user, field, None):
            val = getattr(user, field)
            if val and val.strip():
                return val.strip()
    return None


def _missing_key_msg(provider_id: str) -> str:
    cfg = PROVIDERS.get(provider_id, {})
    return (f'Kein {provider_id}-API-Key hinterlegt. Trage deinen eigenen Key '
            f'unter /research/keys/ ein. (Kein Fallback aus der Server-Konfiguration.)')


# (obsolet, durch obige Implementierung ersetzt)


# -- Protokoll-Adapter ---------------------------------------------------------

def _call_openai_compat(url: str, api_key: str, model: str, prompt: str,
                        max_tokens: int = 1500, timeout: int = 120) -> tuple[str, dict]:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': max_tokens,
    }
    req = urllib.request.Request(url, method='POST',
                                 data=json.dumps(payload).encode(),
                                 headers={
                                     'Content-Type': 'application/json',
                                     'Authorization': f'Bearer {api_key}',
                                 })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    text = body['choices'][0]['message']['content']
    usage = body.get('usage', {})
    tokens = {
        'input': int(usage.get('prompt_tokens', 0)),
        'output': int(usage.get('completion_tokens', 0)),
    }
    return text, tokens


def _call_anthropic(url: str, api_key: str, model: str, prompt: str,
                    max_tokens: int = 1500, timeout: int = 120) -> tuple[str, dict]:
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    req = urllib.request.Request(url, method='POST',
                                 data=json.dumps(payload).encode(),
                                 headers={
                                     'Content-Type': 'application/json',
                                     'x-api-key': api_key,
                                     'anthropic-version': '2023-06-01',
                                 })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    text = body['content'][0]['text']
    usage = body.get('usage', {})
    tokens = {
        'input': int(usage.get('input_tokens', 0)),
        'output': int(usage.get('output_tokens', 0)),
    }
    return text, tokens


def _call_gemini(url_template: str, api_key: str, model: str, prompt: str,
                 max_tokens: int = 1500, timeout: int = 120) -> tuple[str, dict]:
    url = url_template.format(model=model) + f'?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': max_tokens},
    }
    req = urllib.request.Request(url, method='POST',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    text = body['candidates'][0]['content']['parts'][0]['text']
    um = body.get('usageMetadata', {})
    tokens = {
        'input': int(um.get('promptTokenCount', 0)),
        'output': int(um.get('candidatesTokenCount', 0)),
    }
    return text, tokens


def calculate_cost(model_id: str, tokens: dict) -> float:
    """Berechne Kosten in USD basierend auf MODELS[...].pricing (per 1M tokens)."""
    cfg = MODELS.get(model_id)
    if not cfg:
        return 0.0
    pin, pout = cfg['pricing']
    return (tokens.get('input', 0) / 1_000_000) * pin + \
           (tokens.get('output', 0) / 1_000_000) * pout


def _call_one(model_id: str, prompt: str, user, max_tokens: int = 1500,
              timeout: int = 120) -> dict:
    cfg = MODELS.get(model_id)
    if not cfg:
        return {'model': model_id, 'ok': False, 'error': f'Unbekanntes Modell: {model_id}'}
    name = cfg['name']
    provider_id = cfg['provider']
    model_name = cfg['model']
    api_key = _get_api_key(user, provider_id)
    if not api_key:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': _missing_key_msg(provider_id),
                'cost_usd': 0.0}
    prov = PROVIDERS[provider_id]
    url = prov['url']
    api = prov['api']
    t0 = time.time()
    try:
        if api == 'anthropic':
            text, tokens = _call_anthropic(url, api_key, model_name, prompt, max_tokens, timeout)
        elif api == 'gemini':
            text, tokens = _call_gemini(url, api_key, model_name, prompt, max_tokens, timeout)
        else:
            text, tokens = _call_openai_compat(url, api_key, model_name, prompt, max_tokens, timeout)
        cost = calculate_cost(model_id, tokens)
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': True, 'text': text, 'duration_s': time.time() - t0,
                'tokens': tokens, 'cost_usd': cost}
    except urllib.error.HTTPError as e:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': f'HTTP {e.code}: {e.read()[:200].decode(errors="ignore")}',
                'duration_s': time.time() - t0, 'cost_usd': 0.0}
    except Exception as e:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': f'{type(e).__name__}: {e}',
                'duration_s': time.time() - t0, 'cost_usd': 0.0}


def ask_council(question: str, user, model_ids: list[str],
                max_tokens: int = 1500, timeout: int = 120) -> dict:
    """Parallel an alle Modelle. Gibt strukturierte Ergebnisliste zurück."""
    t0 = time.time()
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(model_ids))) as pool:
        futs = {pool.submit(_call_one, m, question, user, max_tokens, timeout): m
                for m in model_ids}
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())
    # Stabile Sortierung wie in model_ids
    idx = {m: i for i, m in enumerate(model_ids)}
    results.sort(key=lambda r: idx.get(r['model'], 999))
    total_cost = sum(r.get('cost_usd', 0) or 0 for r in results)
    return {
        'results': results,
        'duration_s': time.time() - t0,
        'models_used': model_ids,
        'total_cost_usd': total_cost,
    }

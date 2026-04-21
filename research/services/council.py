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


# Verfügbare Modelle (id → (Anzeigename, Provider, Modell-Identifier))
MODELS = {
    'opus':     ('Claude Opus 4.7',        'anthropic',  'claude-opus-4-7'),
    'sonnet':   ('Claude Sonnet 4.6',      'anthropic',  'claude-sonnet-4-6'),
    'haiku':    ('Claude Haiku 4.5',       'anthropic',  'claude-haiku-4-5-20251001'),
    'gpt':      ('GPT-5.4',                'openrouter', 'openai/gpt-5.4'),
    'gemini':   ('Gemini 3.1 Pro',         'gemini',     'gemini-3.1-pro-preview'),
    'grok':     ('Grok 4.20',              'openrouter', 'x-ai/grok-4.20'),
    'deepseek': ('DeepSeek Reasoner',      'deepseek',   'deepseek-reasoner'),
    'glm':      ('GLM 5.1',                'zhipu',      'glm-5.1'),
    'kimi':     ('Kimi K2',                'openrouter', 'moonshotai/kimi-k2-instruct'),
    'qwen':     ('Qwen 3.6 Plus',          'openrouter', 'qwen/qwen3.6-plus'),
    'mistral':  ('Mistral Large 3',        'openrouter', 'mistralai/mistral-large-3-675b-instruct-2512'),
    'minimax':  ('MiniMax M2.7',           'openrouter', 'minimax/minimax-m2.7'),
    'nemotron': ('NVIDIA Nemotron 120B',   'openrouter', 'nvidia/nemotron-3-super-120b-a12b:free'),
    'mercury':  ('Mercury 2',              'openrouter', 'inception/mercury-2'),
}


def display_name(model_id: str) -> str:
    m = MODELS.get(model_id)
    return m[0] if m else model_id


# -- Key-Auflösung -------------------------------------------------------------

USER_KEY_FIELDS = {
    # Mapping: Provider-id → CustomUser-Feld
    'anthropic': 'anthropic_api_key',
    'openai': 'openai_api_key',
    'gemini': 'google_api_key',
}


def _get_api_key(user, provider_id: str) -> str | None:
    """Hole API-Key: erst User-Profil, dann settings, dann env."""
    field = USER_KEY_FIELDS.get(provider_id)
    if field and user and getattr(user, field, None):
        return getattr(user, field).strip()
    prov = PROVIDERS.get(provider_id, {})
    env_name = prov.get('env')
    if env_name:
        val = getattr(settings, env_name, None) or os.environ.get(env_name)
        if val:
            return val.strip()
    return None


# -- Protokoll-Adapter ---------------------------------------------------------

def _call_openai_compat(url: str, api_key: str, model: str, prompt: str,
                        max_tokens: int = 1500, timeout: int = 120) -> str:
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
    return body['choices'][0]['message']['content']


def _call_anthropic(url: str, api_key: str, model: str, prompt: str,
                    max_tokens: int = 1500, timeout: int = 120) -> str:
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
    return body['content'][0]['text']


def _call_gemini(url_template: str, api_key: str, model: str, prompt: str,
                 max_tokens: int = 1500, timeout: int = 120) -> str:
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
    return body['candidates'][0]['content']['parts'][0]['text']


def _call_one(model_id: str, prompt: str, user, max_tokens: int = 1500,
              timeout: int = 120) -> dict:
    cfg = MODELS.get(model_id)
    if not cfg:
        return {'model': model_id, 'ok': False, 'error': f'Unbekanntes Modell: {model_id}'}
    name, provider_id, model_name = cfg
    api_key = _get_api_key(user, provider_id)
    if not api_key:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': f'Kein API-Key für {provider_id}'}
    prov = PROVIDERS[provider_id]
    url = prov['url']
    api = prov['api']
    t0 = time.time()
    try:
        if api == 'anthropic':
            text = _call_anthropic(url, api_key, model_name, prompt, max_tokens, timeout)
        elif api == 'gemini':
            text = _call_gemini(url, api_key, model_name, prompt, max_tokens, timeout)
        else:
            text = _call_openai_compat(url, api_key, model_name, prompt, max_tokens, timeout)
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': True, 'text': text, 'duration_s': time.time() - t0}
    except urllib.error.HTTPError as e:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': f'HTTP {e.code}: {e.read()[:200].decode(errors="ignore")}',
                'duration_s': time.time() - t0}
    except Exception as e:
        return {'model': model_id, 'display': name, 'provider': provider_id,
                'ok': False, 'error': f'{type(e).__name__}: {e}',
                'duration_s': time.time() - t0}


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
    return {
        'results': results,
        'duration_s': time.time() - t0,
        'models_used': model_ids,
    }

"""Multi-Provider LLM-Client fuer Magvis.

Routet je nach MagvisSettings.text_provider auf den richtigen API-Endpoint:
- OpenAI-kompatibel (OpenAI, Z.AI, DeepSeek, OpenRouter)
- Anthropic (Claude)
- Google Gemini (text-Modus, ohne Bild)

Interface kompatibel mit MagvisGLMClient (chat, text, json_chat,
json_chat_with_retry, generate_text — fuer OpenClaw-Skripte).
"""
from __future__ import annotations

import json
import logging
import re

import requests

from ..llm_providers import PROVIDERS

logger = logging.getLogger(__name__)


class MagvisLLMClient:
    TIMEOUT = 180

    def __init__(self, user, magvis_settings=None):
        self.user = user
        self.settings = magvis_settings

        if magvis_settings:
            self.provider_slug = (magvis_settings.text_provider or 'zhipu').lower()
            self.model = magvis_settings.text_model or 'glm-5.1'
        else:
            self.provider_slug = 'zhipu'
            self.model = 'glm-5.1'

        self.cfg = PROVIDERS.get(self.provider_slug, PROVIDERS['zhipu'])
        self.api_key = getattr(user, self.cfg['key_attr'], None)
        self.base_url = self.cfg['base_url']
        self.compat = self.cfg['compat']

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ---------- main API ------------------------------------------------------

    def chat(self, messages, temperature: float = 0.7, max_tokens: int | None = None) -> str:
        if not self.is_configured():
            raise RuntimeError(
                f'Kein API-Key fuer Provider "{self.provider_slug}" konfiguriert. '
                f'Bitte unter /accounts/neue-api-einstellungen/ "{self.cfg["key_attr"]}" setzen.'
            )

        if self.compat == 'openai':
            return self._chat_openai(messages, temperature, max_tokens)
        if self.compat == 'anthropic':
            return self._chat_anthropic(messages, temperature, max_tokens)
        if self.compat == 'gemini':
            return self._chat_gemini(messages, temperature, max_tokens)
        raise NotImplementedError(f'Unbekannter Compat-Mode: {self.compat}')

    def text(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        return self.chat(messages, temperature=temperature)

    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        """OpenClaw-Skript-Adapter (Quiz/Minigame/TOC erwarten dieses Interface)."""
        return self.text(prompt, temperature=0.7)

    def json_chat(self, prompt: str, system: str | None = None,
                  temperature: float = 0.4) -> dict | list:
        full_system = (system or '') + '\n\nAntworte NUR mit gueltigem JSON. Keine Erklaerungen, kein Markdown.'
        text = self.text(prompt, system=full_system, temperature=temperature)
        return _parse_json_loose(text)

    def json_chat_with_retry(self, prompt: str, system: str | None = None,
                              expect: str = 'object', max_tokens: int = 2048,
                              retries: int = 3) -> dict | list | None:
        full_system = (system or '') + ('\n\n' if system else '') + (
            'Antworte AUSSCHLIESSLICH mit gueltigem JSON. Kein Markdown, '
            'keine Erklaerungen, keine Kommentare.'
        )
        for _ in range(retries):
            try:
                text = self.chat(
                    [{'role': 'system', 'content': full_system},
                     {'role': 'user', 'content': prompt}],
                    temperature=0.4, max_tokens=max_tokens,
                )
            except Exception:
                continue
            try:
                result = _parse_json_loose(text)
            except Exception:
                continue
            if expect == 'array' and not isinstance(result, list):
                continue
            if expect == 'object' and not isinstance(result, dict):
                continue
            return result
        return None

    # ---------- provider implementations -------------------------------------

    def _chat_openai(self, messages, temperature, max_tokens) -> str:
        url = self.base_url.rstrip('/') + '/chat/completions'
        payload = {'model': self.model, 'messages': messages, 'temperature': temperature}
        if max_tokens:
            payload['max_tokens'] = max_tokens
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        if self.provider_slug == 'openrouter':
            headers['HTTP-Referer'] = 'https://www.workloom.de'
            headers['X-Title'] = 'Magvis (Workloom)'
        resp = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']

    def _chat_anthropic(self, messages, temperature, max_tokens) -> str:
        # Anthropic: system extern, user/assistant in messages
        system_msg = ''
        clean_msgs = []
        for m in messages:
            if m['role'] == 'system':
                system_msg = m['content']
            else:
                clean_msgs.append({'role': m['role'], 'content': m['content']})

        url = self.base_url.rstrip('/') + '/messages'
        payload = {
            'model': self.model,
            'max_tokens': max_tokens or 4096,
            'temperature': temperature,
            'messages': clean_msgs,
        }
        if system_msg:
            payload['system'] = system_msg
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get('content', [{}])[0].get('text', '')

    def _chat_gemini(self, messages, temperature, max_tokens) -> str:
        # Gemini: system_instruction extern, contents = user/model
        system_msg = ''
        contents = []
        for m in messages:
            if m['role'] == 'system':
                system_msg = m['content']
            else:
                role = 'user' if m['role'] == 'user' else 'model'
                contents.append({'role': role, 'parts': [{'text': m['content']}]})

        url = (self.base_url.rstrip('/') +
               f'/models/{self.model}:generateContent?key={self.api_key}')
        payload = {
            'contents': contents,
            'generationConfig': {
                'temperature': temperature,
                'maxOutputTokens': max_tokens or 4096,
            },
        }
        if system_msg:
            payload['systemInstruction'] = {'parts': [{'text': system_msg}]}

        resp = requests.post(url, json=payload, timeout=self.TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get('candidates', [])
        if not candidates:
            return ''
        parts = candidates[0].get('content', {}).get('parts', [])
        return ''.join(p.get('text', '') for p in parts if 'text' in p)


# ---------- Backwards-compat: alter Klassenname als Alias ---------------------

class MagvisGLMClient(MagvisLLMClient):
    """Alias fuer Backwards-Compat. Wird wie der alte GLM-Client verwendet,
    routet aber jetzt ueber den Multi-Provider-Layer."""
    pass


# ---------- JSON-Parsing -----------------------------------------------------

def _parse_json_loose(text: str):
    """Robustes JSON-Parsing — entfernt Markdown, repariert Trailing-Commas,
    schneidet abgeschnittene Arrays/Objekte."""
    if not text:
        raise ValueError('Leere LLM-Antwort')
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    candidates = []
    for opener, closer in (('[', ']'), ('{', '}')):
        s = text.find(opener)
        e = text.rfind(closer)
        if s != -1 and e > s:
            candidates.append(text[s:e + 1])
    for cand in candidates:
        cand_clean = re.sub(r',(\s*[\]\}])', r'\1', cand)
        try:
            return json.loads(cand_clean)
        except json.JSONDecodeError:
            pass

    for opener, closer in (('[', ']'), ('{', '}')):
        s = text.find(opener)
        if s == -1:
            continue
        positions = [i for i, ch in enumerate(text) if ch == closer and i > s]
        for end in reversed(positions):
            candidate = re.sub(r',(\s*[\]\}])', r'\1', text[s:end + 1])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError(f'Konnte LLM-Antwort nicht als JSON parsen: {text[:200]}...')


def repair_and_parse(text: str, expect: str = 'object'):
    """OpenClaw-kompatibler Wrapper."""
    if not text:
        return None
    try:
        result = _parse_json_loose(text)
    except Exception:
        return None
    if expect == 'array' and not isinstance(result, list):
        return None
    if expect == 'object' and not isinstance(result, dict):
        return None
    return result

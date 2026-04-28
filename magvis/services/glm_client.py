"""GLM-5.1 Client (z.AI) — OpenAI-kompatibler HTTP-Client.

Liest API-Key aus user.zhipu_api_key (EncryptedCharField in accounts.CustomUser).
Nutzt requests, kein SDK.
"""
import json
import logging
import re

import requests

logger = logging.getLogger(__name__)


class MagvisGLMClient:
    DEFAULT_BASE_URL = 'https://api.z.ai/api/coding/paas/v4'
    DEFAULT_MODEL = 'glm-5.1'
    TIMEOUT = 180

    def __init__(self, user, magvis_settings=None):
        self.user = user
        self.api_key = getattr(user, 'zhipu_api_key', None)

        if magvis_settings:
            self.model = magvis_settings.glm_model or self.DEFAULT_MODEL
            self.base_url = magvis_settings.glm_base_url or self.DEFAULT_BASE_URL
        else:
            self.model = self.DEFAULT_MODEL
            self.base_url = self.DEFAULT_BASE_URL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages, temperature: float = 0.7, max_tokens: int | None = None) -> str:
        if not self.is_configured():
            raise RuntimeError(
                'GLM API-Key fehlt. Bitte unter /accounts/api-einstellungen/ "zhipu_api_key" setzen.'
            )

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
        }
        if max_tokens:
            payload['max_tokens'] = max_tokens

        url = self.base_url.rstrip('/') + '/chat/completions'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        response = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']

    def text(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        return self.chat(messages, temperature=temperature)

    def json_chat(self, prompt: str, system: str | None = None, temperature: float = 0.4) -> dict | list:
        """Erzwingt JSON-Antwort. Robust gegen Markdown-Codeblöcke und kaputte Quotes."""
        full_system = (system or '') + '\n\nAntworte NUR mit gültigem JSON. Keine Erklärungen, kein Markdown.'
        text = self.text(prompt, system=full_system, temperature=temperature)
        return _parse_json_loose(text)

    # OpenClaw-Adapter: Quiz/Minigame/TOC erwarten gemini_client.generate_text(prompt, max_tokens=)
    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        return self.text(prompt, temperature=0.7)


def repair_and_parse(text: str, expect: str = 'object'):
    """OpenClaw-kompatibler Wrapper. Liefert dict / list oder None bei Fehler."""
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


def _parse_json_loose(text: str):
    """Parst JSON robust: entfernt Markdown-Codeblöcke, findet JSON in Text."""
    if not text:
        raise ValueError('Leere GLM-Antwort')

    # Markdown-Codeblock entfernen
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: erstes { ... } oder [ ... ] im Text suchen
    for opener, closer in (('{', '}'), ('[', ']')):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f'Konnte GLM-Antwort nicht als JSON parsen: {text[:200]}...')

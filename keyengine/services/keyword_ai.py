import json
import logging
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from openai import OpenAI

logger = logging.getLogger(__name__)
User = get_user_model()


class KeywordAIService:
    """
    Service für KI-gestützte Keyword-Generierung und Intent-Klassifikation
    """

    def __init__(self, user: User):
        self.user = user

        # Hole OpenAI API-Key aus User-Profil (über CentralAPIClient Pattern)
        try:
            from makeads.api_client import CentralAPIClient
            api_client = CentralAPIClient(user)
            api_keys = api_client.get_api_keys()
            self.api_key = api_keys.get('openai')
        except Exception as e:
            logger.warning(f"Could not load API key from CentralAPIClient: {e}")
            self.api_key = None

        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning(f"No OpenAI API key found for user {user.username}")

    def generate_keywords(
        self,
        seed_keyword: str,
        count: int = 25,
        language: str = 'de'
    ) -> Dict[str, Any]:
        """
        Generiert verwandte Keywords basierend auf einem Seed-Keyword

        Args:
            seed_keyword: Das Ausgangs-Keyword
            count: Anzahl der zu generierenden Keywords
            language: Sprache (de/en)

        Returns:
            Dict mit 'success', 'keywords' (List) und optional 'error'
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Kein OpenAI API-Key konfiguriert. Bitte in den Einstellungen einen Key hinterlegen.'
            }

        try:
            # System Prompt
            system_prompt = """Du bist ein SEO-Experte spezialisiert auf Keyword-Research.
Deine Aufgabe ist es, verwandte Long-Tail-Keywords zu generieren und deren Search Intent zu klassifizieren.

Search Intent Kategorien:
- Informational: Nutzer sucht Informationen (z.B. "wie funktioniert...", "was ist...")
- Commercial: Nutzer recherchiert vor Kauf (z.B. "beste...", "vergleich...", "test...")
- Transactional: Nutzer möchte kaufen/handeln (z.B. "kaufen", "bestellen", "mieten")
- Navigational: Nutzer sucht spezifische Website (z.B. Markennamen)
- Local: Lokale Suche (z.B. "in meiner nähe", Stadt-Namen)

Du kannst auch eigene, spezifischere Intent-Kategorien definieren wenn passend."""

            # User Prompt
            user_prompt = f"""Generiere {count} verwandte Long-Tail-Keywords für das Seed-Keyword: "{seed_keyword}"

Anforderungen:
- Verschiedene Variationen und Perspektiven
- Mix aus verschiedenen Intent-Typen
- Natürliche, realistische Suchbegriffe
- Deutsche Sprache (falls nicht anders spezifiziert)

Antworte NUR mit einem JSON-Array im folgenden Format (ohne zusätzlichen Text):
[
  {{
    "keyword": "konkretes long-tail keyword",
    "intent": "intent-kategorie",
    "description": "Kurze Beschreibung in 1 Satz"
  }}
]"""

            # API Call
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Schnell und günstig
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=3000,
                response_format={"type": "json_object"}  # Erzwinge JSON
            )

            # Parse Response
            content = response.choices[0].message.content

            # Versuche JSON zu parsen
            try:
                # Manchmal wrapped OpenAI das Array in ein Object
                parsed = json.loads(content)

                # Wenn es ein Dict ist, suche nach dem Array
                if isinstance(parsed, dict):
                    # Suche nach dem keywords-Key oder dem ersten Array-Value
                    keywords = None
                    for key, value in parsed.items():
                        if isinstance(value, list):
                            keywords = value
                            break
                    if not keywords:
                        raise ValueError("No array found in response")
                else:
                    keywords = parsed

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}\nContent: {content}")
                return {
                    'success': False,
                    'error': f'Fehler beim Parsen der AI-Antwort: {str(e)}'
                }

            # Validiere Struktur
            validated_keywords = []
            for kw in keywords:
                if isinstance(kw, dict) and 'keyword' in kw:
                    validated_keywords.append({
                        'keyword': kw.get('keyword', '').strip(),
                        'intent': kw.get('intent', 'unknown').strip(),
                        'description': kw.get('description', '').strip()
                    })

            if not validated_keywords:
                return {
                    'success': False,
                    'error': 'Keine validen Keywords in der AI-Antwort gefunden'
                }

            logger.info(f"Generated {len(validated_keywords)} keywords for '{seed_keyword}'")

            return {
                'success': True,
                'keywords': validated_keywords,
                'seed_keyword': seed_keyword
            }

        except Exception as e:
            logger.error(f"Error generating keywords: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Fehler bei der Keyword-Generierung: {str(e)}'
            }

    def has_api_key(self) -> bool:
        """Prüft ob ein API-Key verfügbar ist"""
        return self.api_key is not None

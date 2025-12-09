import json
import logging
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from openai import OpenAI

logger = logging.getLogger(__name__)
User = get_user_model()


class QuestionAIService:
    """
    Service für KI-gestützte Fragen-Kategorisierung und -Generierung
    """

    def __init__(self, user: User):
        self.user = user

        # Hole OpenAI API-Key über CentralAPIClient
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

    def categorize_questions(
        self,
        questions: List[str],
        keyword: str
    ) -> Dict[str, Any]:
        """
        Kategorisiert Fragen nach Intent und Thema

        Args:
            questions: Liste von Fragen
            keyword: Das ursprüngliche Keyword

        Returns:
            {
                'success': bool,
                'categorized': [
                    {
                        'question': str,
                        'intent': str,
                        'category': str
                    }
                ],
                'error': str (optional)
            }
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Kein OpenAI API-Key konfiguriert.'
            }

        if not questions:
            return {
                'success': True,
                'categorized': []
            }

        try:
            system_prompt = """Du bist ein SEO-Experte spezialisiert auf Search Intent Analyse.
Deine Aufgabe ist es, Suchfragen zu analysieren und zu kategorisieren.

Intent-Kategorien:
- informational: User sucht Informationen (z.B. "Wie funktioniert...", "Was ist...")
- commercial: User recherchiert vor Kauf (z.B. "Beste...", "Test...", "Vergleich...")
- transactional: User möchte handeln/kaufen (z.B. "kaufen", "Preis", "bestellen")
- navigational: User sucht spezifische Website/Marke

Themen-Kategorien (Beispiele):
- Preis: Fragen zu Kosten, Preisen
- Anleitung: How-to, Tutorials
- Vergleich: Produktvergleiche, Alternativen
- Probleme: Fehlerbehebung, Lösungen
- Eigenschaften: Features, Spezifikationen
- Allgemein: Grundlegende Informationen
"""

            user_prompt = f"""Analysiere folgende Fragen zum Thema "{keyword}" und kategorisiere sie.

Fragen:
{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(questions))}

Antworte NUR mit einem JSON-Objekt im folgenden Format:
{{"questions": [
  {{
    "question": "Die Frage",
    "intent": "informational|commercial|transactional|navigational",
    "category": "Themen-Kategorie"
  }}
]}}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            parsed = json.loads(content)

            # Array extrahieren
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if isinstance(value, list):
                        categorized = value
                        break
                else:
                    categorized = []
            else:
                categorized = parsed

            return {
                'success': True,
                'categorized': categorized
            }

        except Exception as e:
            logger.error(f"Error categorizing questions: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Fehler bei der Kategorisierung: {str(e)}'
            }

    def generate_additional_questions(
        self,
        keyword: str,
        existing_questions: List[str] = None,
        count: int = 10
    ) -> Dict[str, Any]:
        """
        Generiert zusätzliche relevante Fragen mit KI

        Args:
            keyword: Das Keyword
            existing_questions: Bereits vorhandene Fragen (zur Vermeidung von Duplikaten)
            count: Anzahl zu generierender Fragen

        Returns:
            {
                'success': bool,
                'questions': [
                    {
                        'question': str,
                        'intent': str,
                        'category': str
                    }
                ],
                'error': str (optional)
            }
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Kein OpenAI API-Key konfiguriert.'
            }

        try:
            existing_str = ""
            if existing_questions:
                existing_str = f"\n\nBereits vorhandene Fragen (nicht wiederholen):\n" + \
                              "\n".join(f"- {q}" for q in existing_questions[:10])

            system_prompt = """Du bist ein SEO-Content-Stratege.
Generiere relevante Fragen, die potenzielle Kunden zu einem Thema stellen würden.
Die Fragen sollten:
- Natürlich klingen
- Verschiedene Intentionen abdecken
- Für Content-Erstellung nützlich sein"""

            user_prompt = f"""Generiere {count} relevante Fragen zum Thema: "{keyword}"

Achte auf:
- Mix aus informational, commercial und transactional Fragen
- Verschiedene Themen-Aspekte abdecken
- Deutsche Sprache{existing_str}

Antworte NUR mit einem JSON-Objekt:
{{"questions": [
  {{
    "question": "Die Frage?",
    "intent": "informational|commercial|transactional",
    "category": "Themen-Kategorie"
  }}
]}}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            parsed = json.loads(content)

            # Array extrahieren
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if isinstance(value, list):
                        questions = value
                        break
                else:
                    questions = []
            else:
                questions = parsed

            return {
                'success': True,
                'questions': questions
            }

        except Exception as e:
            logger.error(f"Error generating questions: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Fehler bei der Generierung: {str(e)}'
            }

    def has_api_key(self) -> bool:
        """Prüft ob ein API-Key verfügbar ist"""
        return self.api_key is not None

"""
Video Service für BlogPrep

Verantwortlich für:
- Video-Skript generieren (nur gesprochener Text)
- Diagramm-Analyse und Vorschläge
"""

import logging
import json
import re
import time
from typing import Dict, List, Optional

# Optionale Imports - werden nur bei Bedarf geladen
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class VideoService:
    """Service für Video-Skript und Diagramm-Generierung"""

    # Durchschnittliche Wörter pro Minute beim Sprechen
    WORDS_PER_MINUTE = 130

    def __init__(self, user, settings=None):
        """
        Initialisiert den Video Service.

        Args:
            user: Django User Objekt mit API-Keys
            settings: Optional BlogPrepSettings Objekt
        """
        self.user = user
        self.settings = settings

        # Provider und Modell aus Settings oder Defaults
        if settings:
            self.provider = settings.ai_provider
            self.model = settings.ai_model
        else:
            self.provider = 'openai'
            self.model = 'gpt-4o'

        # Clients initialisieren
        self._init_clients()

    def _init_clients(self):
        """Initialisiert die API-Clients basierend auf Provider"""
        self.openai_client = None
        self.gemini_model = None
        self.anthropic_client = None

        if self.provider == 'openai' and OPENAI_AVAILABLE and self.user.openai_api_key:
            self.openai_client = OpenAI(api_key=self.user.openai_api_key)
        elif self.provider == 'gemini' and GENAI_AVAILABLE and self.user.gemini_api_key:
            genai.configure(api_key=self.user.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.model)
        elif self.provider == 'anthropic' and ANTHROPIC_AVAILABLE and self.user.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=self.user.anthropic_api_key)

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 3000, temperature: float = 0.7) -> Dict:
        """Ruft das LLM auf basierend auf dem konfigurierten Provider."""
        start_time = time.time()

        try:
            if self.provider == 'openai' and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                content = response.choices[0].message.content.strip()
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0

            elif self.provider == 'gemini' and self.gemini_model:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                response = self.gemini_model.generate_content(
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature
                    )
                )
                content = response.text.strip()
                tokens_in = 0
                tokens_out = 0

            elif self.provider == 'anthropic' and self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = response.content[0].text.strip()
                tokens_in = response.usage.input_tokens if response.usage else 0
                tokens_out = response.usage.output_tokens if response.usage else 0

            else:
                return {
                    'success': False,
                    'error': f'API-Key für {self.provider} nicht konfiguriert'
                }

            duration = time.time() - start_time

            return {
                'success': True,
                'content': content,
                'tokens_input': tokens_in,
                'tokens_output': tokens_out,
                'duration': duration
            }

        except Exception as e:
            logger.error(f"LLM call error ({self.provider}): {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_json_response(self, content: str) -> Optional[Dict]:
        """Versucht JSON aus der LLM-Antwort zu extrahieren"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    def generate_video_script(
        self,
        duration_minutes: int,
        blog_content: str,
        keyword: str,
        company_name: str = ''
    ) -> Dict:
        """
        Generiert ein Video-Skript basierend auf dem Blog-Content.

        Args:
            duration_minutes: Gewünschte Video-Länge in Minuten
            blog_content: Der vollständige Blog-Content
            keyword: Das Hauptkeyword
            company_name: Name des Unternehmens (für Personalisierung)

        Returns:
            Dict mit success, script (nur gesprochener Text)
        """
        target_words = duration_minutes * self.WORDS_PER_MINUTE

        system_prompt = f"""Du bist ein erfahrener Video-Skript-Autor.
Du schreibst NUR den gesprochenen Text für Videos - keine Regieanweisungen, keine Rollenbezeichnungen, keine Szenenanweisungen.
Der Text soll natürlich klingen, als würde jemand frei sprechen.
{"Du sprichst im Namen von " + company_name + "." if company_name else ""}"""

        user_prompt = f"""Erstelle ein Video-Skript zum Thema "{keyword}" basierend auf diesem Blog-Content:

{blog_content[:4000]}

ANFORDERUNGEN:
- Dauer: ca. {duration_minutes} Minuten ({target_words} Wörter)
- NUR gesprochener Text
- KEINE Regieanweisungen wie "[Sprecher]", "(Pause)", "[Schnitt]", etc.
- KEINE Rollenbezeichnungen
- Natürlicher, fließender Sprachstil
- Persönliche Ansprache ("du" oder "Sie" passend zum Blog)
- Klare Struktur mit Einleitung, Hauptteil, Schluss
- Wichtige Punkte betonen durch Wiederholung

Das Skript beginnt DIREKT mit dem gesprochenen Text.
Schreibe {target_words} Wörter."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=4000, temperature=0.8)

        if result['success']:
            # Bereinige eventuell verbliebene Anweisungen
            script = result['content']
            script = re.sub(r'\[.*?\]', '', script)  # Entferne [Anweisungen]
            script = re.sub(r'\(.*?\)', '', script)  # Entferne (Anweisungen)
            script = re.sub(r'^[A-Z]+:', '', script, flags=re.MULTILINE)  # Entferne ROLLE:
            script = re.sub(r'\n{3,}', '\n\n', script)  # Mehrfache Zeilenumbrüche reduzieren
            script = script.strip()

            word_count = len(script.split())
            estimated_duration = round(word_count / self.WORDS_PER_MINUTE, 1)

            return {
                'success': True,
                'script': script,
                'word_count': word_count,
                'estimated_duration_minutes': estimated_duration,
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0)
            }

        return result

    def analyze_for_diagram(self, blog_content: str, keyword: str) -> Dict:
        """
        Analysiert den Blog-Content und schlägt ein passendes Diagramm vor.

        Args:
            blog_content: Der vollständige Blog-Content
            keyword: Das Hauptkeyword

        Returns:
            Dict mit diagram_type, title, data, reasoning
        """
        system_prompt = """Du bist ein Datenvisualisierungs-Experte.
Analysiere Texte und schlage das beste Diagramm vor, um die Kernaussagen zu visualisieren."""

        user_prompt = f"""Analysiere diesen Blog-Content zum Thema "{keyword}" und schlage ein passendes Diagramm vor:

{blog_content[:3000]}

MÖGLICHE DIAGRAMMTYPEN:
- bar: Balkendiagramm (für Vergleiche, Rankings)
- pie: Tortendiagramm (für Anteile, Verteilungen)
- line: Liniendiagramm (für Trends, Entwicklungen)
- comparison: Vergleichstabelle (für Pro/Contra, Optionen)
- flow: Flussdiagramm (für Prozesse, Schritte)
- timeline: Zeitstrahl (für chronologische Abläufe)

Erstelle als JSON:
{{
    "diagram_type": "bar|pie|line|comparison|flow|timeline",
    "title": "Aussagekräftiger Titel für das Diagramm",
    "labels": ["Label1", "Label2", "Label3", "Label4", "Label5"],
    "values": [30, 25, 20, 15, 10],
    "reasoning": "Kurze Begründung warum dieses Diagramm passt"
}}

WICHTIG:
- Wähle den Diagrammtyp der die Kernaussage am besten visualisiert
- Extrahiere echte Daten/Kategorien aus dem Text
- Bei fehlenden Zahlen: schätze realistische Werte
- Maximal 5-7 Datenpunkte für Übersichtlichkeit

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=1000)

        if not result['success']:
            return result

        parsed = self._parse_json_response(result['content'])
        if parsed:
            return {
                'success': True,
                'data': parsed,
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0)
            }

        return {
            'success': False,
            'error': 'Konnte Diagramm-Analyse nicht parsen',
            'raw_content': result['content']
        }

    def suggest_diagram_improvements(self, diagram_data: Dict, user_feedback: str) -> Dict:
        """
        Verbessert Diagramm-Daten basierend auf User-Feedback.

        Args:
            diagram_data: Aktuelle Diagramm-Daten
            user_feedback: Feedback vom Benutzer

        Returns:
            Dict mit verbesserten Diagramm-Daten
        """
        system_prompt = """Du bist ein Datenvisualisierungs-Experte.
Verbessere Diagramm-Vorschläge basierend auf Benutzer-Feedback."""

        user_prompt = f"""Verbessere dieses Diagramm basierend auf dem Feedback:

AKTUELLES DIAGRAMM:
{json.dumps(diagram_data, ensure_ascii=False, indent=2)}

BENUTZER-FEEDBACK:
{user_feedback}

Erstelle eine verbesserte Version als JSON mit derselben Struktur:
{{
    "diagram_type": "...",
    "title": "...",
    "labels": [...],
    "values": [...],
    "reasoning": "Was wurde geändert"
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=800)

        if not result['success']:
            return result

        parsed = self._parse_json_response(result['content'])
        if parsed:
            return {
                'success': True,
                'data': parsed
            }

        return {
            'success': False,
            'error': 'Konnte verbesserte Daten nicht parsen'
        }

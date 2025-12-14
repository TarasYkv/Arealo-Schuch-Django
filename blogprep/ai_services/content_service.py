"""
Content Service für BlogPrep

Verantwortlich für:
- Web-Recherche und Konkurrenzanalyse
- Gliederung erstellen
- Blog-Content generieren (Intro, Main, Tips)
- FAQs generieren
- SEO-Meta generieren
"""

import logging
import json
import re
import time
from typing import Dict, List, Optional, Any

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


class ContentService:
    """Service für KI-gestützte Content-Generierung"""

    def __init__(self, user, settings=None):
        """
        Initialisiert den Content Service.

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

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> Dict:
        """
        Ruft das LLM auf basierend auf dem konfigurierten Provider.

        Returns:
            Dict mit 'success', 'content' oder 'error'
        """
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
                tokens_in = 0  # Gemini gibt keine Token-Info
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
            # Versuche direkt zu parsen
            return json.loads(content)
        except json.JSONDecodeError:
            # Versuche JSON aus Markdown-Codeblock zu extrahieren
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # Versuche JSON-Objekt zu finden
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        return None

    def analyze_research(self, keyword: str, search_results: List[Dict]) -> Dict:
        """
        Analysiert Web-Recherche-Ergebnisse und extrahiert wichtige Informationen.

        Args:
            keyword: Das Hauptkeyword
            search_results: Liste von Suchergebnissen mit title, snippet, url

        Returns:
            Dict mit topics, related_keywords, questions
        """
        system_prompt = """Du bist ein SEO-Experte und Content-Stratege.
Analysiere die Suchergebnisse und extrahiere die wichtigsten Informationen für einen Blogbeitrag."""

        # Formatiere Suchergebnisse
        results_text = ""
        for i, result in enumerate(search_results[:10], 1):
            results_text += f"\n{i}. {result.get('title', '')}\n"
            results_text += f"   {result.get('snippet', '')}\n"

        user_prompt = f"""Analysiere diese Suchergebnisse zum Keyword "{keyword}":

{results_text}

Erstelle eine strukturierte Analyse als JSON:

{{
    "main_topics": ["Die 5-7 wichtigsten Themen die behandelt werden"],
    "related_keywords": ["10-15 verwandte Keywords und Suchbegriffe"],
    "user_questions": ["8-10 häufige Fragen die Nutzer haben"],
    "pain_points": ["5 Hauptprobleme/Herausforderungen der Zielgruppe"],
    "content_gaps": ["Was fehlt in den bestehenden Artikeln?"]
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=1500)

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
            'error': 'Konnte JSON nicht parsen',
            'raw_content': result['content']
        }

    def generate_outline(self, keyword: str, secondary_keywords: List[str], research_data: Dict) -> Dict:
        """
        Generiert eine Blog-Gliederung basierend auf Keyword und Recherche.

        Args:
            keyword: Hauptkeyword
            secondary_keywords: Liste sekundärer Keywords
            research_data: Ergebnisse der Recherche-Analyse

        Returns:
            Dict mit outline (Liste von H2-Überschriften)
        """
        system_prompt = """Du bist ein erfahrener Content-Stratege und SEO-Experte.
Erstelle eine perfekte Blog-Gliederung die sowohl für Leser als auch Suchmaschinen optimiert ist."""

        topics = research_data.get('main_topics', [])
        questions = research_data.get('user_questions', [])

        user_prompt = f"""Erstelle eine Blog-Gliederung zum Thema "{keyword}".

SEKUNDÄRE KEYWORDS: {', '.join(secondary_keywords) if secondary_keywords else 'Keine'}

WICHTIGE THEMEN AUS DER RECHERCHE:
{chr(10).join(f'- {t}' for t in topics)}

HÄUFIGE NUTZERFRAGEN:
{chr(10).join(f'- {q}' for q in questions)}

ANFORDERUNGEN:
- 4-6 H2-Überschriften
- Gesamtlänge: ca. 2400 Wörter (verteilt auf die Abschnitte)
- Lesedauer: 8-10 Minuten
- Keyword "{keyword}" natürlich in Überschriften integrieren
- Sekundäre Keywords sinnvoll einbauen

STRUKTUR:
1. Einleitung mit persönlichem Einstieg
2. Hauptteil mit konkreten Informationen/Tipps
3. Do's und Don'ts oder Checkliste
4. FAQ-Bereich

Erstelle als JSON:
{{
    "outline": [
        {{
            "h2": "Überschrift",
            "section": "intro|main|tips",
            "word_target": 800,
            "key_points": ["Punkt 1", "Punkt 2"]
        }}
    ],
    "total_word_target": 2400
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=1500)

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
            'error': 'Konnte JSON nicht parsen',
            'raw_content': result['content']
        }

    def generate_content_section(
        self,
        section_type: str,
        keyword: str,
        outline_section: Dict,
        company_info: Dict,
        writing_style: str = 'du'
    ) -> Dict:
        """
        Generiert einen Content-Abschnitt (Intro, Main, Tips).

        Args:
            section_type: 'intro', 'main', oder 'tips'
            keyword: Hauptkeyword
            outline_section: Gliederung für diesen Abschnitt
            company_info: Unternehmensinformationen
            writing_style: 'du', 'sie', oder 'neutral'

        Returns:
            Dict mit content (HTML-formatierter Text)
        """
        style_instructions = {
            'du': 'Schreibe persönlich in der "du"-Form. Sei nahbar und freundlich.',
            'sie': 'Schreibe formell in der "Sie"-Form. Bleibe professionell.',
            'neutral': 'Schreibe neutral ohne direkte Anrede. Verwende passive Formulierungen.'
        }

        section_prompts = {
            'intro': f"""Schreibe die EINLEITUNG (ca. 800 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Persönlicher Einstieg mit eigener Erfahrung aus Sicht des Unternehmens
- Erkläre warum das Thema wichtig ist
- Nenne Kriterien für gute Entscheidungen
- Verwende Aufzählungen und fette wichtige Begriffe
- Baue das Keyword natürlich ein (2-3 mal)

UNTERNEHMEN: {company_info.get('name', '')}
EXPERTISE: {company_info.get('expertise', '')}

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong> Tags.
Beginne DIREKT mit dem Content, keine Überschrift.""",

            'main': f"""Schreibe den HAUPTTEIL (ca. 800 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Präsentiere konkrete Empfehlungen/Informationen
- Unterteile in übersichtliche Kategorien
- Füge eine Vergleichstabelle ein (HTML <table>)
- Verweise subtil auf Produkte/Dienstleistungen des Unternehmens
- Begründe Empfehlungen mit Fakten oder Erfahrung

UNTERNEHMEN: {company_info.get('name', '')}
PRODUKTE: {company_info.get('products', '')}

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong>, <table>, <h3> Tags.
Beginne DIREKT mit dem Content, keine H2-Überschrift (die kommt separat).""",

            'tips': f"""Schreibe den TIPPS-BEREICH (ca. 800 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Detaillierte Liste von Do's und Don'ts
- Erkläre häufige Fehler und wie man sie vermeidet
- Gib wertvolle, praktische Tipps
- Nutze Tabellen für Übersichtlichkeit
- Teile persönliche Erfahrungen

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong>, <table>, <h3> Tags.
Beginne DIREKT mit dem Content, keine H2-Überschrift."""
        }

        system_prompt = f"""Du bist ein erfahrener Content-Writer der informative, persönliche Blogbeiträge schreibt.
Du schreibst aus der Perspektive von "{company_info.get('name', 'einem Experten')}" und teilst echte Erfahrungen.
Dein Stil ist {writing_style}-Form, informativ aber nicht werblich."""

        user_prompt = section_prompts.get(section_type, section_prompts['main'])

        result = self._call_llm(system_prompt, user_prompt, max_tokens=2500, temperature=0.8)

        if result['success']:
            return {
                'success': True,
                'content': result['content'],
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0)
            }

        return result

    def generate_faqs(self, keyword: str, research_data: Dict, content_summary: str = '') -> Dict:
        """
        Generiert 5 FAQs zum Thema.

        Args:
            keyword: Hauptkeyword
            research_data: Recherche-Daten mit user_questions
            content_summary: Zusammenfassung des bisherigen Contents

        Returns:
            Dict mit faqs Liste [{question, answer}]
        """
        questions = research_data.get('user_questions', [])

        system_prompt = """Du bist ein Experte für FAQ-Erstellung die sowohl nutzerfreundlich als auch SEO-optimiert sind.
Erstelle FAQs die echte Nutzerfragen beantworten und für Featured Snippets optimiert sind."""

        user_prompt = f"""Erstelle 5 FAQs zum Thema "{keyword}".

HÄUFIGE NUTZERFRAGEN AUS DER RECHERCHE:
{chr(10).join(f'- {q}' for q in questions)}

ANFORDERUNGEN:
- 5 relevante Fragen die Nutzer wirklich haben
- Ausführliche, hilfreiche Antworten (je 50-100 Wörter)
- Einfache, verständliche Sprache
- Keyword natürlich integrieren
- Schema.org FAQ-optimiert

Erstelle als JSON:
{{
    "faqs": [
        {{
            "question": "Die Frage?",
            "answer": "Die ausführliche Antwort..."
        }}
    ]
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=2000)

        if not result['success']:
            return result

        parsed = self._parse_json_response(result['content'])
        if parsed and 'faqs' in parsed:
            return {
                'success': True,
                'faqs': parsed['faqs'],
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0)
            }

        return {
            'success': False,
            'error': 'Konnte FAQs nicht parsen',
            'raw_content': result['content']
        }

    def generate_seo_meta(self, keyword: str, content_summary: str) -> Dict:
        """
        Generiert SEO-Titel, Meta-Description und Zusammenfassung.

        Args:
            keyword: Hauptkeyword
            content_summary: Kurze Zusammenfassung des Contents

        Returns:
            Dict mit title, description, summary
        """
        system_prompt = """Du bist ein SEO-Spezialist der perfekte Meta-Daten für Suchmaschinen erstellt.
Deine Titel und Descriptions erzielen hohe Klickraten."""

        user_prompt = f"""Erstelle SEO-Meta-Daten für einen Blogbeitrag zum Thema "{keyword}".

CONTENT-ZUSAMMENFASSUNG:
{content_summary[:500] if content_summary else 'Informativer Blogbeitrag zum Thema'}

ANFORDERUNGEN:
- SEO-Titel: Max. 60 Zeichen, Keyword am Anfang, clickbait-frei aber ansprechend
- Meta-Description: Max. 155 Zeichen, Call-to-Action, Keyword enthalten
- Zusammenfassung: 50-70 Wörter für Social Media Sharing

Erstelle als JSON:
{{
    "title": "Der SEO-optimierte Titel",
    "description": "Die Meta-Description...",
    "summary": "Die prägnante Zusammenfassung für Social Media..."
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=500)

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
            'error': 'Konnte SEO-Meta nicht parsen',
            'raw_content': result['content']
        }

    def suggest_keywords(self, main_keyword: str) -> Dict:
        """
        Schlägt sekundäre Keywords basierend auf dem Hauptkeyword vor.

        Args:
            main_keyword: Das Hauptkeyword

        Returns:
            Dict mit keywords Liste
        """
        system_prompt = """Du bist ein SEO-Keyword-Experte.
Schlage relevante sekundäre Keywords vor die semantisch zum Hauptkeyword passen."""

        user_prompt = f"""Schlage 8-10 sekundäre Keywords für "{main_keyword}" vor.

KRITERIEN:
- Semantisch verwandt
- Suchintention ähnlich
- Mix aus Long-Tail und Short-Tail
- In Deutschland gebräuchlich

Erstelle als JSON:
{{
    "keywords": ["keyword1", "keyword2", ...]
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=300)

        if not result['success']:
            return result

        parsed = self._parse_json_response(result['content'])
        if parsed and 'keywords' in parsed:
            return {
                'success': True,
                'keywords': parsed['keywords']
            }

        return {
            'success': False,
            'error': 'Konnte Keywords nicht parsen'
        }

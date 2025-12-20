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


def _get_user_friendly_error(error: Exception, provider: str) -> str:
    """
    Wandelt API-Fehler in benutzerfreundliche deutsche Fehlermeldungen um.
    """
    error_str = str(error).lower()

    # OpenAI spezifische Fehler
    if 'insufficient_quota' in error_str or 'exceeded your current quota' in error_str:
        return (
            f"⚠️ OpenAI API-Guthaben erschöpft!\n\n"
            f"Mögliche Ursachen:\n"
            f"• Kein Guthaben auf dem OpenAI-Konto\n"
            f"• Keine Zahlungsmethode hinterlegt\n"
            f"• Projekt-Budget-Limit erreicht\n"
            f"• Trial-Credits aufgebraucht\n\n"
            f"Lösung:\n"
            f"1. Öffne https://platform.openai.com/account/billing/overview\n"
            f"2. Prüfe ob Guthaben vorhanden ist oder füge Zahlungsmethode hinzu\n"
            f"3. Prüfe Projekt-Limits unter Settings → Limits\n\n"
            f"Alternativ: Wechsle zu Gemini oder Anthropic in den Einstellungen."
        )

    if 'rate_limit' in error_str or 'rate limit' in error_str:
        return (
            f"⏳ Rate-Limit erreicht ({provider})\n\n"
            f"Du hast zu viele Anfragen in kurzer Zeit gesendet.\n"
            f"Warte 1-2 Minuten und versuche es erneut."
        )

    if 'invalid_api_key' in error_str or 'invalid api key' in error_str or 'incorrect api key' in error_str:
        return (
            f"🔑 Ungültiger API-Key ({provider})\n\n"
            f"Der gespeicherte API-Key ist ungültig oder wurde widerrufen.\n"
            f"Bitte aktualisiere deinen API-Key in den Profil-Einstellungen."
        )

    if 'authentication' in error_str or 'unauthorized' in error_str:
        return (
            f"🔐 Authentifizierungsfehler ({provider})\n\n"
            f"Der API-Key konnte nicht authentifiziert werden.\n"
            f"Prüfe deinen API-Key in den Profil-Einstellungen."
        )

    if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
        return (
            f"🌐 Verbindungsfehler ({provider})\n\n"
            f"Konnte keine Verbindung zum API-Server herstellen.\n"
            f"Bitte versuche es in einigen Sekunden erneut."
        )

    if 'model_not_found' in error_str or 'model not found' in error_str:
        return (
            f"🤖 Modell nicht verfügbar ({provider})\n\n"
            f"Das gewählte KI-Modell ist nicht verfügbar.\n"
            f"Wähle ein anderes Modell in den Einstellungen."
        )

    # Generischer Fehler
    return f"❌ API-Fehler ({provider}): {str(error)}"


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
            user_friendly_error = _get_user_friendly_error(e, self.provider)
            return {
                'success': False,
                'error': user_friendly_error
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
        Analysiert echte Web-Recherche-Ergebnisse und extrahiert wichtige Informationen.

        Args:
            keyword: Das Hauptkeyword
            search_results: Liste von Suchergebnissen mit title, snippet, url, content

        Returns:
            Dict mit topics, related_keywords, questions
        """
        system_prompt = """Du bist ein SEO-Experte und Content-Stratege.
Analysiere die echten Suchergebnisse aus dem Web und extrahiere die wichtigsten Informationen für einen Blogbeitrag.
Du erhältst die tatsächlichen Inhalte der Top-Suchergebnisse."""

        # Formatiere Suchergebnisse mit echtem Inhalt
        results_text = ""
        for i, result in enumerate(search_results[:5], 1):
            results_text += f"\n{'='*50}\n"
            results_text += f"SUCHERGEBNIS {i}:\n"
            results_text += f"Titel: {result.get('title', '')}\n"
            results_text += f"URL: {result.get('url', '')}\n"
            results_text += f"Snippet: {result.get('snippet', '')}\n"

            # Füge den extrahierten Seiteninhalt hinzu
            content = result.get('content', '') or result.get('content_preview', '')
            if content:
                # Begrenze den Inhalt pro Ergebnis
                content_preview = content[:1500] + '...' if len(content) > 1500 else content
                results_text += f"\nSEITENINHALT:\n{content_preview}\n"

        # Falls keine Ergebnisse, nur Keyword-basierte Analyse
        if not results_text.strip():
            results_text = f"(Keine Suchergebnisse verfügbar - analysiere basierend auf Keyword '{keyword}')"

        user_prompt = f"""Analysiere diese echten Web-Suchergebnisse zum Keyword "{keyword}":

{results_text}

WICHTIG: Basiere deine Analyse auf den TATSÄCHLICHEN INHALTEN der gefundenen Seiten.
Identifiziere:
- Welche Themen werden von den Top-Ergebnissen behandelt?
- Welche Keywords/Begriffe werden häufig verwendet?
- Welche Fragen werden beantwortet?
- Was fehlt in den bestehenden Artikeln?

Erstelle eine strukturierte Analyse als JSON:

{{
    "main_topics": ["Die 5-7 wichtigsten Themen die in den Ergebnissen behandelt werden"],
    "related_keywords": ["10-15 verwandte Keywords und Begriffe aus den Inhalten"],
    "user_questions": ["8-10 Fragen die die Artikel beantworten oder die Nutzer haben könnten"],
    "pain_points": ["5 Hauptprobleme/Herausforderungen die angesprochen werden"],
    "content_gaps": ["Was fehlt in den bestehenden Artikeln? Was könnten wir besser machen?"],
    "key_facts": ["5-8 wichtige Fakten/Statistiken/Tipps aus den Artikeln"]
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=2000)

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
        Generiert eine ausführliche Blog-Gliederung basierend auf Keyword und Recherche.

        Args:
            keyword: Hauptkeyword
            secondary_keywords: Liste sekundärer Keywords
            research_data: Ergebnisse der Recherche-Analyse

        Returns:
            Dict mit outline (Liste von H2-Überschriften)
        """
        system_prompt = """Du bist ein erfahrener Content-Stratege und SEO-Experte.
Erstelle eine AUSFÜHRLICHE und DETAILLIERTE Blog-Gliederung basierend auf der Web-Recherche.
Deine Gliederung muss die Erkenntnisse aus der Konkurrenzanalyse aufgreifen und BESSER sein als die analysierten Artikel."""

        topics = research_data.get('main_topics', [])
        questions = research_data.get('user_questions', [])
        key_facts = research_data.get('key_facts', [])
        pain_points = research_data.get('pain_points', [])
        content_gaps = research_data.get('content_gaps', [])
        related_keywords = research_data.get('related_keywords', [])

        user_prompt = f"""Erstelle eine AUSFÜHRLICHE Blog-Gliederung zum Thema "{keyword}".

=== RECHERCHE-ERGEBNISSE (aus Top-5 Suchergebnissen) ===

HAUPTTHEMEN DIE BEHANDELT WERDEN:
{chr(10).join(f'- {t}' for t in topics) if topics else '- Keine Daten'}

WICHTIGE FAKTEN & ERKENNTNISSE:
{chr(10).join(f'- {f}' for f in key_facts) if key_facts else '- Keine Daten'}

HÄUFIGE NUTZERFRAGEN:
{chr(10).join(f'- {q}' for q in questions) if questions else '- Keine Daten'}

PROBLEME & HERAUSFORDERUNGEN DER ZIELGRUPPE:
{chr(10).join(f'- {p}' for p in pain_points) if pain_points else '- Keine Daten'}

CONTENT-LÜCKEN (was die Konkurrenz NICHT gut macht):
{chr(10).join(f'- {g}' for g in content_gaps) if content_gaps else '- Keine Daten'}

VERWANDTE KEYWORDS:
{', '.join(related_keywords[:10]) if related_keywords else 'Keine'}

SEKUNDÄRE KEYWORDS:
{', '.join(secondary_keywords) if secondary_keywords else 'Keine'}

=== ANFORDERUNGEN AN DIE GLIEDERUNG ===

1. NUTZE DIE RECHERCHE-ERGEBNISSE:
   - Greife die identifizierten Themen auf
   - Beantworte die häufigen Nutzerfragen
   - Adressiere die Pain Points der Zielgruppe
   - Schließe die Content-Lücken der Konkurrenz

2. STRUKTUR:
   - 5-7 H2-Überschriften (mehr Detail = besser)
   - Gesamtlänge: ca. 1600-1800 Wörter (Einleitung ~400, Hauptteil ~600, Tipps ~600)
   - Lesedauer: 6-8 Minuten
   - Jeder Abschnitt mit 3-5 konkreten Key Points

3. ABSCHNITTE:
   - Einleitung (~400 Wörter): Persönlicher Einstieg, Problem aufgreifen, Mehrwert versprechen
   - Hauptteil (~600 Wörter): Grundlagen, Empfehlungen, Vergleiche
   - Tipps & Do's/Don'ts (~600 Wörter): Praktische Anleitungen, häufige Fehler
   - Fazit: Zusammenfassung + Call-to-Action

4. SEO-OPTIMIERUNG:
   - Keyword "{keyword}" in mindestens 2 H2-Überschriften
   - Sekundäre Keywords natürlich einbauen
   - Überschriften als Fragen formulieren (wo sinnvoll)

Erstelle als JSON:
{{
    "outline": [
        {{
            "h2": "Konkrete, aussagekräftige Überschrift",
            "section": "intro|main|tips",
            "word_target": 400,
            "key_points": ["Detaillierter Punkt 1", "Detaillierter Punkt 2", "Detaillierter Punkt 3"],
            "research_reference": "Welche Recherche-Erkenntnisse hier einfließen"
        }}
    ],
    "total_word_target": 1600,
    "unique_angle": "Was macht diesen Artikel besser als die Konkurrenz?"
}}

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=2500)

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

        # Produktlinks formatieren für Prompts
        product_links = company_info.get('product_links', [])
        product_links_text = ""
        if product_links:
            product_links_text = "\n\nPRODUKTVERLINKUNGEN (füge diese natürlich im Text ein wo passend):\n"
            for p in product_links:
                product_links_text += f'- <a href="{p.get("url", "")}">{p.get("name", "")}</a>\n'
            product_links_text += "\nWICHTIG: Verlinke mindestens 1-2 Produkte natürlich im Text, wenn sie thematisch passen!"

        section_prompts = {
            'intro': f"""Schreibe die EINLEITUNG (ca. 400 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Persönlicher Einstieg mit eigener Erfahrung aus Sicht des Unternehmens
- Erkläre warum das Thema wichtig ist
- Nenne Kriterien für gute Entscheidungen
- Verwende Aufzählungen und fette wichtige Begriffe
- Baue das Keyword natürlich ein (2-3 mal)
- WICHTIG: Halte dich an max. 400 Wörter!

UNTERNEHMEN: {company_info.get('name', '')}
EXPERTISE: {company_info.get('expertise', '')}{product_links_text}

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong>, <a> Tags.
Beginne DIREKT mit dem Content, keine Überschrift.""",

            'main': f"""Schreibe den HAUPTTEIL (ca. 600 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Präsentiere konkrete Empfehlungen/Informationen
- Unterteile in übersichtliche Kategorien
- Füge eine Vergleichstabelle ein (HTML <table>)
- Verweise subtil auf Produkte/Dienstleistungen des Unternehmens
- Begründe Empfehlungen mit Fakten oder Erfahrung
- WICHTIG: Halte dich an max. 600 Wörter!

UNTERNEHMEN: {company_info.get('name', '')}
PRODUKTE: {company_info.get('products', '')}{product_links_text}

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong>, <table>, <h3>, <a> Tags.
Beginne DIREKT mit dem Content, keine H2-Überschrift (die kommt separat).""",

            'tips': f"""Schreibe den TIPPS-BEREICH (ca. 600 Wörter) für einen Blogbeitrag zum Thema "{keyword}".

ÜBERSCHRIFT: {outline_section.get('h2', '')}
WICHTIGE PUNKTE: {', '.join(outline_section.get('key_points', []))}

ANFORDERUNGEN:
- Detaillierte Liste von Do's und Don'ts
- Erkläre häufige Fehler und wie man sie vermeidet
- Gib wertvolle, praktische Tipps
- Nutze Tabellen für Übersichtlichkeit
- Teile persönliche Erfahrungen
- WICHTIG: Halte dich an max. 600 Wörter!
{product_links_text}

{style_instructions.get(writing_style, style_instructions['du'])}

Formatiere als HTML mit <p>, <ul>, <li>, <strong>, <table>, <h3>, <a> Tags.
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

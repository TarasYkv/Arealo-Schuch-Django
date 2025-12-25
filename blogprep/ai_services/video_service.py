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

# Import der gemeinsamen Fehlerbehandlung
from .content_service import _get_user_friendly_error


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
            user_friendly_error = _get_user_friendly_error(e, self.provider)
            return {
                'success': False,
                'error': user_friendly_error
            }

    def _parse_json_response(self, content: str) -> Optional[Dict]:
        """Versucht JSON aus der LLM-Antwort zu extrahieren"""
        if not content:
            return None

        content = content.strip()

        # Direktes Parsen
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Markdown-Codeblock extrahieren
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        return None

    # Blog-basierte Skript-Art Prompts
    SCRIPT_TYPE_PROMPTS = {
        'summary': {
            'name': 'Zusammenfassung',
            'instructions': """Fasse die wichtigsten Punkte des Blogbeitrags zusammen.
- Beginne mit einem starken Einstieg der das Thema vorstellt
- Nenne die 3-5 wichtigsten Erkenntnisse
- Schließe mit einem klaren Fazit ab"""
        },
        'fun_facts': {
            'name': 'Witzige Fakten',
            'instructions': """Erstelle ein unterhaltsames Skript mit witzigen, überraschenden Fakten zum Thema.
- Beginne mit "Wusstest du, dass..."
- Verwende humorvolle Überleitungen
- Überrasche mit unerwarteten Zusammenhängen
- Halte den Ton locker und unterhaltsam
- Füge 1-2 lustige Vergleiche ein"""
        },
        'interesting_facts': {
            'name': 'Interessante Fakten',
            'instructions': """Präsentiere faszinierende, wissenswerte Fakten zum Thema.
- Starte mit dem interessantesten Fakt als Hook
- Erkläre Hintergründe und Zusammenhänge
- Verwende konkrete Zahlen und Beispiele
- Verknüpfe Fakten miteinander
- Schließe mit einem "Wow-Moment" ab"""
        },
        'how_to': {
            'name': 'How-To Anleitung',
            'instructions': """Erstelle eine klare Schritt-für-Schritt Anleitung.
- Beginne mit dem Ziel: "In diesem Video zeige ich dir, wie..."
- Nummeriere die Schritte klar durch
- Erkläre jeden Schritt verständlich
- Gib praktische Tipps bei jedem Schritt
- Fasse am Ende zusammen"""
        },
        'tips': {
            'name': 'Tipps & Tricks',
            'instructions': """Präsentiere die besten Tipps und Tricks kompakt.
- Starte mit "Hier sind meine Top-Tipps für..."
- Nummeriere jeden Tipp
- Halte jeden Tipp kurz und prägnant
- Erkläre warum jeder Tipp funktioniert
- Füge einen Bonus-Tipp am Ende hinzu"""
        },
        'pros_cons': {
            'name': 'Vor- und Nachteile',
            'instructions': """Stelle Vor- und Nachteile übersichtlich gegenüber.
- Beginne mit einer neutralen Einführung
- Liste zuerst die Vorteile auf
- Dann die Nachteile ehrlich benennen
- Gib eine ausgewogene Empfehlung
- Schließe mit "Für wen ist das geeignet?" ab"""
        },
        'faq': {
            'name': 'FAQ',
            'instructions': """Beantworte die häufigsten Fragen zum Thema.
- Beginne mit "Die häufigsten Fragen zu..."
- Stelle jede Frage klar
- Beantworte kurz und verständlich
- Verwende Beispiele zur Verdeutlichung
- Schließe mit der wichtigsten Frage ab"""
        },
        'storytelling': {
            'name': 'Storytelling',
            'instructions': """Erzähle eine packende Geschichte rund ums Thema.
- Beginne mit einem persönlichen Erlebnis oder einer Situation
- Baue Spannung auf
- Verwebe Informationen in die Geschichte
- Schaffe eine emotionale Verbindung
- Schließe mit einer Lektion oder Erkenntnis ab"""
        },
        'hook': {
            'name': 'Social Media Hook',
            'instructions': """Erstelle einen aufmerksamkeitsstarken Hook für Social Media.
- Beginne mit einer provokanten Aussage oder Frage
- Erzeuge sofort Neugier ("Das hat mich schockiert...")
- Halte das Tempo hoch
- Verwende kurze, knackige Sätze
- Ende mit einem Call-to-Action"""
        },
        'product_highlight': {
            'name': 'Produkt-Highlight',
            'instructions': """Stelle Produkte oder Dienstleistungen in den Fokus.
- Beginne mit dem Problem das gelöst wird
- Präsentiere die Lösung/das Produkt
- Nenne konkrete Vorteile und Features
- Füge Social Proof ein (wenn verfügbar)
- Schließe mit einem Angebot oder Call-to-Action ab"""
        }
    }

    # Keyword-basierte Skript-Art Prompts (ohne Blog-Content, mit "du"-Form)
    KEYWORD_SCRIPT_PROMPTS = {
        'kw_fun_facts': {
            'name': 'Witzige Fakten',
            'instructions': """Erstelle witzige, überraschende Fakten zum Thema.
- Beginne mit "Wusstest du, dass..."
- Verwende humorvolle, unterhaltsame Fakten
- Überrasche mit unerwarteten Zusammenhängen
- Halte den Ton locker und lustig
- Die Fakten sollen zum Schmunzeln bringen
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_interesting_facts': {
            'name': 'Interessante Fakten',
            'instructions': """Präsentiere faszinierende, wissenswerte Fakten zum Thema.
- Starte mit dem interessantesten Fakt als Hook
- Verwende konkrete Zahlen und Beispiele
- Verknüpfe Fakten miteinander
- Schließe mit einem "Wow-Moment" ab
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_sayings': {
            'name': 'Unterhaltsame Sprüche',
            'instructions': """Erstelle witzige, unterhaltsame Sprüche zum Thema.
- Schreibe lockere, lustige Sprüche
- Verwende Wortspiele wenn möglich
- Halte die Sprüche kurz und prägnant
- Die Sprüche sollen zum Teilen animieren
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_story': {
            'name': 'Spannende Geschichte',
            'instructions': """Erzähle eine spannende, fesselnde Geschichte zum Thema.
- Beginne mit einem packenden Einstieg
- Baue Spannung auf
- Schaffe eine emotionale Verbindung
- Die Geschichte soll unterhalten und fesseln
- Schließe mit einem überraschenden oder berührenden Ende
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_true_false': {
            'name': 'Wahr oder Falsch',
            'instructions': """Erstelle eine "Wahr oder Falsch" Geschichte.
- Erzähle eine unglaubliche aber wahre Geschichte ODER eine erfundene Geschichte
- Baue die Geschichte spannend auf
- Halte den Zuschauer in Spannung
- Am Ende auflösen ob es wahr oder falsch ist
- Erkläre kurz warum
- Sprich den Zuschauer direkt mit "du" an (z.B. "Glaubst du, das stimmt?")"""
        },
        'kw_tongue_twister': {
            'name': 'Zungenbrecher',
            'instructions': """Erstelle einen lustigen Zungenbrecher zum Thema.
- Der Zungenbrecher muss zum Thema passen
- Er soll schwer auszusprechen sein
- Verwende Alliterationen und ähnliche Laute
- Mache ihn lustig und unterhaltsam
- Fordere den Zuschauer auf, es nachzusprechen
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_poem': {
            'name': 'Gedicht',
            'instructions': """Schreibe ein kreatives Gedicht zum Thema.
- Das Gedicht soll sich reimen
- Halte einen gleichmäßigen Rhythmus
- Das Gedicht soll unterhalten oder berühren
- Verwende bildhafte Sprache
- Passe den Ton an das Thema an (witzig, nachdenklich, etc.)
- Sprich den Zuschauer direkt mit "du" an wenn passend"""
        },
        'kw_qa': {
            'name': 'Frage + Antwort',
            'instructions': """Stelle eine spannende Frage und beantworte sie überraschend.
- Beginne mit einer fesselnden Frage
- Baue Spannung auf ("Hast du dich das auch schon gefragt?")
- Gib eine überraschende oder interessante Antwort
- Erkläre den Hintergrund kurz
- Schließe mit einer Erkenntnis ab
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_riddle': {
            'name': 'Rätsel',
            'instructions': """Erstelle ein Rätsel zum Thema.
- Formuliere ein kniffliges Rätsel
- Gib dem Zuschauer Zeit zum Nachdenken (z.B. "Denk mal kurz nach...")
- Die Lösung soll überraschend aber logisch sein
- Löse das Rätsel am Ende auf
- Erkläre kurz warum die Lösung stimmt
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_expectation_reality': {
            'name': 'Erwartung vs. Realität',
            'instructions': """Zeige den lustigen Unterschied zwischen Erwartung und Realität.
- Beschreibe zuerst die typische Erwartung
- Dann die (oft lustige) Realität
- Verwende Kontraste für Humor
- Das Format: "Erwartung: ... Realität: ..."
- Halte es relatable und witzig
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_weird_laws': {
            'name': 'Kuriose Gesetze',
            'instructions': """Präsentiere kuriose, echte Gesetze zum Thema.
- Nenne echte, verrückte Gesetze die mit dem Thema zu tun haben
- Erkläre wo diese Gesetze gelten
- Kommentiere humorvoll wie absurd sie sind
- Die Gesetze müssen ECHT sein (recherchiere!)
- Sprich den Zuschauer direkt mit "du" an"""
        },
        'kw_nonsense': {
            'name': 'Dinge ohne Sinn',
            'instructions': """Zeige Dinge zum Thema, die einfach keinen Sinn ergeben.
- Liste absurde, unsinnige Dinge auf
- Kommentiere humorvoll warum sie keinen Sinn machen
- Verwende Ironie und Humor
- Halte den Ton locker und unterhaltsam
- Rege zum Nachdenken und Lachen an
- Sprich den Zuschauer direkt mit "du" an"""
        }
    }

    def generate_video_script(
        self,
        duration_minutes: int,
        blog_content: str,
        keyword: str,
        company_name: str = '',
        script_type: str = 'summary'
    ) -> Dict:
        """
        Generiert ein Video-Skript basierend auf dem Blog-Content.

        Args:
            duration_minutes: Gewünschte Video-Länge in Minuten
            blog_content: Der vollständige Blog-Content
            keyword: Das Hauptkeyword
            company_name: Name des Unternehmens (für Personalisierung)
            script_type: Art des Skripts (summary, fun_facts, etc.)

        Returns:
            Dict mit success, script (nur gesprochener Text)
        """
        target_words = duration_minutes * self.WORDS_PER_MINUTE

        # Hole Skript-Art spezifische Anweisungen
        script_config = self.SCRIPT_TYPE_PROMPTS.get(script_type, self.SCRIPT_TYPE_PROMPTS['summary'])
        script_name = script_config['name']
        script_instructions = script_config['instructions']

        system_prompt = f"""Du bist ein erfahrener Video-Skript-Autor.
Du schreibst NUR den gesprochenen Text für Videos - keine Regieanweisungen, keine Rollenbezeichnungen, keine Szenenanweisungen.
Der Text soll natürlich klingen, als würde jemand frei sprechen.
{"Du sprichst im Namen von " + company_name + "." if company_name else ""}

SKRIPT-ART: {script_name}
{script_instructions}"""

        user_prompt = f"""Erstelle ein "{script_name}" Video-Skript zum Thema "{keyword}" basierend auf diesem Blog-Content:

{blog_content[:4000]}

ANFORDERUNGEN:
- Dauer: ca. {duration_minutes} Minuten ({target_words} Wörter)
- NUR gesprochener Text
- KEINE Regieanweisungen wie "[Sprecher]", "(Pause)", "[Schnitt]", etc.
- KEINE Rollenbezeichnungen
- Natürlicher, fließender Sprachstil
- Persönliche Ansprache ("du" oder "Sie" passend zum Blog)

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

    def generate_keyword_script(
        self,
        duration_minutes: float,
        keyword: str,
        script_type: str = 'kw_fun_facts'
    ) -> Dict:
        """
        Generiert ein kreatives Video-Skript NUR basierend auf einem Keyword (ohne Blog-Content).

        Args:
            duration_minutes: Gewünschte Video-Länge in Minuten
            keyword: Das Thema/Keyword
            script_type: Art des Skripts (kw_fun_facts, kw_story, etc.)

        Returns:
            Dict mit success, script (nur gesprochener Text)
        """
        target_words = int(duration_minutes * self.WORDS_PER_MINUTE)

        # Hole Skript-Art spezifische Anweisungen
        script_config = self.KEYWORD_SCRIPT_PROMPTS.get(script_type, self.KEYWORD_SCRIPT_PROMPTS['kw_fun_facts'])
        script_name = script_config['name']
        script_instructions = script_config['instructions']

        system_prompt = f"""Du bist ein kreativer Video-Skript-Autor für Social Media.
Du schreibst NUR den gesprochenen Text für Videos - keine Regieanweisungen, keine Rollenbezeichnungen, keine Szenenanweisungen.
Der Text soll natürlich klingen, als würde jemand frei und locker sprechen.
WICHTIG: Sprich den Zuschauer IMMER mit "du" an (informell).

SKRIPT-ART: {script_name}
{script_instructions}"""

        user_prompt = f"""Erstelle ein "{script_name}" Video-Skript zum Thema: "{keyword}"

ANFORDERUNGEN:
- Dauer: ca. {duration_minutes} Minuten ({target_words} Wörter)
- NUR gesprochener Text
- KEINE Regieanweisungen wie "[Sprecher]", "(Pause)", "[Schnitt]", etc.
- KEINE Rollenbezeichnungen
- Natürlicher, lockerer Sprachstil
- IMMER "du"-Form verwenden
- Unterhaltsam und fesselnd

Das Skript beginnt DIREKT mit dem gesprochenen Text.
Schreibe ca. {target_words} Wörter."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=2000, temperature=0.9)

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
        system_prompt = """Du bist ein Datenvisualisierungs-Experte mit Fokus auf Blog-Content.
Analysiere Texte gründlich und wähle den BESTEN Diagrammtyp basierend auf dem tatsächlichen Inhalt.
VERMEIDE es, immer das gleiche Diagramm zu wählen - analysiere den Content und wähle den passendsten Typ."""

        user_prompt = f"""Analysiere diesen Blog-Content zum Thema "{keyword}" und schlage das BESTE Diagramm vor:

{blog_content[:4000]}

═══════════════════════════════════════════════════════════════════
DIAGRAMMTYPEN UND WANN SIE PASSEN:
═══════════════════════════════════════════════════════════════════

1. VERGLEICHS-DIAGRAMME:
   • bar_vertical: Vertikale Balken - für Rankings, Mengenvergleiche (z.B. "Die 5 wichtigsten Faktoren")
   • bar_horizontal: Horizontale Balken - für lange Labels, Zeitvergleiche (z.B. "Vor vs. Nach")
   • comparison_table: Vergleichstabelle - für Pro/Contra, Feature-Vergleich, Alternativen
   • radar: Spinnendiagramm - für Multi-Kriterien-Bewertung, Stärken/Schwächen-Profile

2. ANTEILS-DIAGRAMME:
   • pie: Kreisdiagramm - NUR wenn Summe 100% ergibt (z.B. Marktanteile, Budgetverteilung)
   • donut: Ringdiagramm - wie Pie, aber moderner, mit Kennzahl in der Mitte
   • stacked_bar: Gestapelte Balken - für Zusammensetzung über mehrere Kategorien

3. TREND-/ZEIT-DIAGRAMME:
   • line: Liniendiagramm - für Entwicklungen über Zeit, Trends, Prognosen
   • area: Flächendiagramm - wie Line, aber mit Betonung der Gesamtmenge
   • timeline: Zeitstrahl - für chronologische Ereignisse, Geschichte, Meilensteine

4. PROZESS-DIAGRAMME:
   • flow: Flussdiagramm - für Abläufe, Entscheidungsbäume, Workflows
   • funnel: Trichterdiagramm - für Conversion-Prozesse, Verkaufstrichter, Filterung
   • steps: Schritte-Diagramm - für Anleitungen, How-To, Phasen

5. SPEZIAL-DIAGRAMME:
   • gauge: Tacho/Messanzeige - für einzelne Kennzahlen, Zielerreichung, Scores
   • checklist: Checkliste visuell - für Anforderungen, Features, Kriterien
   • matrix: 2x2 Matrix - für Prioritäten (wichtig/dringend), Positionierung
   • icons_grid: Icon-Raster - für Feature-Übersicht, Vorteile auf einen Blick

═══════════════════════════════════════════════════════════════════
ANALYSE-AUFGABE:
═══════════════════════════════════════════════════════════════════

1. Lies den Content aufmerksam
2. Identifiziere die KERNAUSSAGE die visualisiert werden soll
3. Finde passende Daten/Kategorien IM TEXT (keine erfundenen!)
4. Wähle den Diagrammtyp der diese Kernaussage am besten transportiert

Erstelle als JSON:
{{
    "diagram_type": "<einer der obigen Typen>",
    "title": "Prägnanter, aussagekräftiger Titel",
    "subtitle": "Optionaler erklärender Untertitel",
    "labels": ["Kategorie1", "Kategorie2", ...],
    "values": [wert1, wert2, ...],
    "value_labels": ["80%", "60%", ...],
    "colors": ["#4CAF50", "#2196F3", ...],
    "center_value": "Falls donut/gauge: Hauptwert in der Mitte",
    "steps": ["Schritt 1", "Schritt 2", ...],
    "axis_label_x": "X-Achsen-Beschriftung (falls line/bar)",
    "axis_label_y": "Y-Achsen-Beschriftung (falls line/bar)",
    "reasoning": "Warum dieser Diagrammtyp am besten passt",
    "key_insight": "Die wichtigste Erkenntnis die der Leser mitnehmen soll"
}}

REGELN:
- Wähle NICHT immer bar_vertical - analysiere was wirklich passt!
- Extrahiere echte Kategorien/Zahlen aus dem Text
- Bei Prozessen/Anleitungen → flow, steps, oder funnel
- Bei Vergleichen → comparison_table, radar, oder bar_horizontal
- Bei Zeitverläufen → timeline, line, oder area
- Bei Anteilen (100%) → pie oder donut
- Bei Checklisten/Features → checklist oder icons_grid
- values müssen zur Aussage passen (nicht immer 30,25,20,15,10!)

Antworte NUR mit dem JSON-Objekt."""

        result = self._call_llm(system_prompt, user_prompt, max_tokens=1500)

        if not result['success']:
            return result

        parsed = self._parse_json_response(result['content'])
        if parsed:
            # Validiere und normalisiere den Diagrammtyp
            valid_types = [
                'bar_vertical', 'bar_horizontal', 'comparison_table', 'radar',
                'pie', 'donut', 'stacked_bar',
                'line', 'area', 'timeline',
                'flow', 'funnel', 'steps',
                'gauge', 'checklist', 'matrix', 'icons_grid',
                # Legacy-Support
                'bar', 'comparison'
            ]

            diagram_type = parsed.get('diagram_type', 'bar_vertical')
            # Normalisiere Legacy-Typen
            if diagram_type == 'bar':
                diagram_type = 'bar_vertical'
            elif diagram_type == 'comparison':
                diagram_type = 'comparison_table'

            if diagram_type not in valid_types:
                diagram_type = 'bar_vertical'

            parsed['diagram_type'] = diagram_type

            return {
                'success': True,
                'data': parsed,
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0)
            }

        # Zeige die ersten 500 Zeichen der KI-Antwort im Fehler
        raw_preview = result['content'][:500] if result.get('content') else 'Keine Antwort'
        return {
            'success': False,
            'error': f'JSON-Parsing fehlgeschlagen. KI-Antwort:\n\n{raw_preview}',
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

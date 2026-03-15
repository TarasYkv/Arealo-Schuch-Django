"""
P-Loom AI Service für Produkttext-Generierung
"""
import json
import logging
from typing import Optional, Dict, Any

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


class PLoomAIService:
    """Service für KI-gestützte Produkttext-Generierung"""

    def __init__(self, user):
        self.user = user
        self.provider = 'openai'
        self.model = 'gpt-4o-mini'
        self.writing_style = 'du'

        # Einstellungen laden wenn vorhanden
        if user and user.is_authenticated:
            from ..models import PLoomSettings
            settings = PLoomSettings.objects.filter(user=user).first()
            if settings:
                self.provider = settings.ai_provider
                self.model = settings.ai_model
                self.writing_style = settings.writing_style

    def _get_api_key(self) -> Optional[str]:
        """Holt den API-Key basierend auf dem Provider"""
        if not self.user or not self.user.is_authenticated:
            return None

        if self.provider == 'openai':
            return self.user.openai_api_key
        elif self.provider == 'anthropic':
            return self.user.anthropic_api_key
        elif self.provider == 'gemini':
            return self.user.gemini_api_key or self.user.google_api_key

        return None

    def _get_style_instruction(self) -> str:
        """Gibt die Anrede-Anweisung zurück"""
        if self.writing_style == 'du':
            return "Verwende die Du-Anrede. Schreibe locker und freundlich."
        elif self.writing_style == 'sie':
            return "Verwende die Sie-Anrede. Schreibe höflich und professionell."
        else:
            return "Schreibe neutral ohne direkte Anrede."

    def _call_openai(self, messages: list) -> Optional[str]:
        """Ruft die OpenAI API auf"""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package nicht installiert")

        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("OpenAI API-Key nicht konfiguriert")

        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        return response.choices[0].message.content

    def _call_anthropic(self, messages: list) -> Optional[str]:
        """Ruft die Anthropic API auf"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic package nicht installiert")

        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("Anthropic API-Key nicht konfiguriert")

        client = anthropic.Anthropic(api_key=api_key)

        # System-Message extrahieren
        system_message = ""
        user_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                user_messages.append(msg)

        response = client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system_message,
            messages=user_messages,
        )

        return response.content[0].text

    def _call_gemini(self, messages: list) -> Optional[str]:
        """Ruft die Gemini API auf"""
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI package nicht installiert")

        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("Gemini API-Key nicht konfiguriert")

        genai.configure(api_key=api_key)

        # Modell initialisieren
        model = genai.GenerativeModel(self.model)

        # Messages zu einem Prompt zusammenfügen
        prompt_parts = []
        for msg in messages:
            if msg['role'] == 'system':
                prompt_parts.append(f"Anweisung: {msg['content']}")
            else:
                prompt_parts.append(msg['content'])

        prompt = "\n\n".join(prompt_parts)

        response = model.generate_content(prompt)
        return response.text

    def _call_ai(self, messages: list) -> Optional[str]:
        """Ruft die entsprechende AI-API auf"""
        if self.provider == 'openai':
            return self._call_openai(messages)
        elif self.provider == 'anthropic':
            return self._call_anthropic(messages)
        elif self.provider == 'gemini':
            return self._call_gemini(messages)
        else:
            raise ValueError(f"Unbekannter Provider: {self.provider}")

    def generate_title(self, product_name: str, keywords: str = "") -> Optional[str]:
        """Generiert einen verkaufsstarken Produkttitel"""
        style_instruction = self._get_style_instruction()

        system_prompt = f"""Du bist ein E-Commerce Experte für Shopify-Produkte.
{style_instruction}

Erstelle einen verkaufsstarken, ansprechenden Produkttitel.

Regeln:
- Maximal 70 Zeichen
- Hauptkeyword am Anfang
- Keine Übertreibungen wie "BESTE" oder "GÜNSTIGSTE"
- Keine Sonderzeichen wie ★ oder ❤
- Professionell aber ansprechend
- Deutsch"""

        user_prompt = f"Produktname: {product_name}"
        if keywords:
            user_prompt += f"\nWichtige Keywords: {keywords}"
        user_prompt += "\n\nErstelle nur den Titel, keine Erklärungen."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            # Bereinigen
            result = result.strip().strip('"').strip("'")
            # Auf 70 Zeichen begrenzen
            if len(result) > 70:
                result = result[:67] + "..."
        return result

    def generate_description(self, product_name: str, keywords: str = "", tone: str = "professional") -> Optional[str]:
        """Generiert eine HTML-formatierte Produktbeschreibung"""
        style_instruction = self._get_style_instruction()

        tone_instructions = {
            "professional": "Professionell und seriös",
            "casual": "Locker und freundlich",
            "enthusiastic": "Begeistert und energiegeladen",
            "luxury": "Elegant und hochwertig",
            "technical": "Technisch und detailliert",
        }
        tone_text = tone_instructions.get(tone, tone_instructions["professional"])

        system_prompt = f"""Du bist ein E-Commerce Copywriter für Shopify-Produkte.
{style_instruction}
Schreibstil: {tone_text}

Erstelle eine ansprechende Produktbeschreibung in HTML.

Regeln:
- 150-300 Wörter
- HTML-Formatierung (p, ul, li, strong, em)
- Beginne mit einem Fließtext, der das Produkt vorstellt
- Dann Vorteile als Aufzählung
- Am Ende ein kurzer Call-to-Action
- Keywords natürlich einbauen
- Keine Übertreibungen oder Falschaussagen
- Deutsch"""

        user_prompt = f"Produktname: {product_name}"
        if keywords:
            user_prompt += f"\nWichtige Keywords/Features: {keywords}"
        user_prompt += "\n\nErstelle nur die HTML-Beschreibung, keine zusätzlichen Erklärungen."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            # Markdown-Code-Blöcke entfernen falls vorhanden
            result = result.strip()
            if result.startswith("```html"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
        return result

    def generate_seo(self, product_name: str, description: str = "", keywords: str = "") -> Optional[Dict[str, str]]:
        """Generiert SEO-Titel und Meta-Description"""
        style_instruction = self._get_style_instruction()

        system_prompt = f"""Du bist ein SEO-Experte für E-Commerce.
{style_instruction}

Erstelle SEO-optimierte Texte für ein Shopify-Produkt.

Regeln für SEO-Titel:
- Maximal 60 Zeichen
- Hauptkeyword am Anfang
- Ansprechend für Klicks
- Kein Clickbait

Regeln für Meta-Description:
- Maximal 155 Zeichen
- Enthält Hauptkeyword
- Call-to-Action oder Nutzenversprechen
- Keine Sonderzeichen

Antworte NUR im JSON-Format:
{{"seo_title": "...", "seo_description": "..."}}"""

        user_prompt = f"Produktname: {product_name}"
        if description:
            user_prompt += f"\nProduktbeschreibung: {description[:500]}"
        if keywords:
            user_prompt += f"\nWichtige Keywords: {keywords}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            try:
                # JSON extrahieren
                result = result.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                result = result.strip()

                data = json.loads(result)

                # Längen prüfen und ggf. kürzen
                if len(data.get('seo_title', '')) > 60:
                    data['seo_title'] = data['seo_title'][:57] + "..."
                if len(data.get('seo_description', '')) > 155:
                    data['seo_description'] = data['seo_description'][:152] + "..."

                return data
            except json.JSONDecodeError:
                logger.error(f"Could not parse SEO JSON: {result}")
                return None
        return None

    def generate_tags(self, product_name: str, description: str = "") -> Optional[str]:
        """Generiert relevante Tags/Keywords"""
        system_prompt = """Du bist ein SEO-Experte für E-Commerce.

Erstelle relevante Tags/Keywords für ein Shopify-Produkt.

Regeln:
- 5-10 Tags
- Komma-getrennt
- Kleinschreibung
- Keine Duplikate
- Mix aus: Produkttyp, Material, Verwendung, Zielgruppe
- Deutsch

Antworte NUR mit den Tags, komma-getrennt, ohne Erklärungen."""

        user_prompt = f"Produktname: {product_name}"
        if description:
            user_prompt += f"\nBeschreibung: {description[:300]}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            # Bereinigen
            result = result.strip()
            # Sicherstellen dass es komma-getrennt ist
            tags = [tag.strip().lower() for tag in result.split(',') if tag.strip()]
            result = ", ".join(tags[:10])  # Max 10 Tags
        return result

    def generate_all_seo_content(self, keyword: str, language: str = "de", context: str = "") -> Optional[Dict[str, str]]:
        """Generiert alle SEO-optimierten Inhalte auf einmal"""
        style_instruction = self._get_style_instruction()

        lang_instruction = "Schreibe auf Deutsch." if language == "de" else "Write in English."

        system_prompt = f"""Du bist ein SEO-Experte und E-Commerce Copywriter.
{style_instruction}
{lang_instruction}

Erstelle SEO-optimierte Produkttexte basierend auf einem Haupt-Keyword.

Fokus auf:
- Suchmaschinenoptimierung (SEO)
- Conversion-Optimierung
- Natürliche Keyword-Integration
- Professioneller Verkaufston

Antworte NUR im JSON-Format mit folgender Struktur:
{{
    "title": "Verkaufsstarker Produkttitel (max 70 Zeichen, Keyword am Anfang)",
    "description": "HTML-formatierte Produktbeschreibung (150-250 Wörter, mit <p>, <ul>, <li>, <strong>)",
    "seo_title": "SEO Meta-Titel (max 60 Zeichen, Keyword am Anfang)",
    "seo_description": "SEO Meta-Beschreibung (max 155 Zeichen, mit Call-to-Action)",
    "tags": "keyword1, keyword2, keyword3 (5-8 relevante Tags, komma-getrennt)"
}}"""

        context_block = ""
        if context:
            context_block = f"""

Nutze folgende Produkt-Informationen als Basis für die Beschreibung:
{context}
"""

        user_prompt = f"""Haupt-Keyword: {keyword}
{context_block}
Erstelle jetzt alle SEO-optimierten Texte für dieses Produkt.
Achte besonders auf:
1. Das Keyword soll natürlich in allen Texten vorkommen
2. Der Titel soll zum Klicken animieren
3. Die Beschreibung soll Vorteile und Features hervorheben
4. Die Meta-Texte sollen in Suchergebnissen gut performen
5. Die Tags sollen für interne Suche und SEO relevant sein"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            try:
                # JSON extrahieren
                result = result.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                result = result.strip()

                data = json.loads(result)

                # Längen prüfen und ggf. kürzen
                if data.get('title') and len(data['title']) > 70:
                    data['title'] = data['title'][:67] + "..."
                if data.get('seo_title') and len(data['seo_title']) > 60:
                    data['seo_title'] = data['seo_title'][:57] + "..."
                if data.get('seo_description') and len(data['seo_description']) > 155:
                    data['seo_description'] = data['seo_description'][:152] + "..."

                # HTML bereinigen
                if data.get('description'):
                    desc = data['description']
                    if desc.startswith("```html"):
                        desc = desc[7:]
                    if desc.startswith("```"):
                        desc = desc[3:]
                    if desc.endswith("```"):
                        desc = desc[:-3]
                    data['description'] = desc.strip()

                return data
            except json.JSONDecodeError:
                logger.error(f"Could not parse all SEO JSON: {result}")
                return None
        return None

    def generate_engraving_suggestions(self, keyword: str, count: int = 16) -> list:
        """Generiert kreative Gravur-Text Vorschläge für Blumentöpfe (emotional + humorvoll)"""
        emotional_count = count // 2 + count % 2  # Mehrheit emotional
        humor_count = count // 2

        system_prompt = f"""Du bist Spezialist für kreative Gravur-Texte auf Blumentöpfen, die als Geschenk überreicht werden.

Generiere ZWEI Kategorien von Gravur-Texten:

### KATEGORIE 1: EMOTIONALE SPRÜCHE ({emotional_count} Stück) ###
- TIEFSINNIG und BEDEUTUNGSVOLL — keine oberflächlichen Floskeln
- EMOTIONAL berühren — der Beschenkte soll beim Lesen einen Moment innehalten
- Wertschätzung, Liebe, Verbundenheit ausdrücken
- Metapher zwischen Pflanze/Wachstum und der Beziehung/dem Anlass

Stilrichtungen:
- Poetisch-philosophisch ("Wurzeln der Liebe", "Wo du blühst, bin ich Zuhause")
- Herzlich-persönlich ("Für dich wächst mein Herz", "Dein Lächeln lässt mich blühen")
- Tiefgründig-metaphorisch ("Gemeinsam Wurzeln schlagen", "Liebe braucht nur Licht")
- Dankbar-wertschätzend ("Du bist mein Sonnenschein", "Danke, dass du blühst")

### KATEGORIE 2: HUMORVOLLE SPRÜCHE ({humor_count} Stück) ###
- WITZIG und CHARMANT — bringt den Beschenkten zum Schmunzeln
- Thematisch passend zum Anlass/zur Zielgruppe
- Wortspiele mit Pflanzen/Blumen/Wachstum sind ideal
- Liebevoll-frech, nicht beleidigend
- Alltagshumor der zum Thema passt

Beispiele für humorvolle Gravuren:
- Zum Thema Mama: "Mama weiß alles. Wenn nicht, googelt sie."
- Zum Thema Gärtner: "Ich rede mit Pflanzen. Die hören wenigstens zu."
- Zum Thema Lehrer: "Danke fürs Gießen kleiner Köpfe"
- Zum Thema Büro: "Überlebt mehr als meine Motivation"

### ALLGEMEINE REGELN ###
- Kurz und prägnant (2-6 Worte pro Text)
- Deutsch
- VERMEIDE generische Sprüche wie "Alles Gute" oder "Viel Glück"
- Zuerst die emotionalen, dann die humorvollen Sprüche

Antworte NUR als JSON-Array mit Strings, z.B.: ["Text 1", "Text 2", ...]"""

        user_prompt = f"Generiere {count} Gravur-Texte zum Thema '{keyword}': {emotional_count} emotionale und {humor_count} humorvolle. Jeder Text soll als Geschenk-Gravur auf einem Blumentopf funktionieren."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            try:
                result = result.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                result = result.strip()
                data = json.loads(result)
                if isinstance(data, list):
                    return data[:count]
            except json.JSONDecodeError:
                logger.error(f"Could not parse engraving suggestions JSON: {result}")
        return []

    def generate_scene_suggestions(self, keyword: str, count: int = 8) -> list:
        """Generiert Hintergrund-Szenen Vorschläge für Produktfotos"""
        system_prompt = """Du bist Spezialist für Produktfotografie-Szenen.
Schlage Hintergrund-Szenen für Produktfotos eines gravierten Blumentopfs vor.
Jede Szene soll eine junge Frau als Model zeigen.

Regeln:
- Szene passend zum Thema
- Natürliche, warme Atmosphäre
- Jede Szene mit einer jungen Frau die den Topf hält/präsentiert
- Verschiedene Settings (Innen, Außen, Jahreszeiten)
- Detaillierte Beschreibung für KI-Bildgenerierung

Antworte NUR als JSON-Array mit Objekten: [{"title": "...", "description": "..."}]"""

        user_prompt = f"Schlage {count} Hintergrund-Szenen für Produktfotos eines gravierten Blumentopfs zum Thema '{keyword}' vor."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            try:
                result = result.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                result = result.strip()
                data = json.loads(result)
                if isinstance(data, list):
                    return data[:count]
            except json.JSONDecodeError:
                logger.error(f"Could not parse scene suggestions JSON: {result}")
        return []

    def generate_alt_texts(self, keyword: str, scenes: list, engraving_text: str) -> list:
        """Generiert Alt-Texte für Produktbilder"""
        system_prompt = """Du bist SEO-Experte für E-Commerce Bildoptimierung.
Erstelle beschreibende Alt-Texte für Produktbilder eines gravierten Blumentopfs.

Regeln:
- Max 125 Zeichen pro Alt-Text
- Beschreibend und keyword-reich
- Natürliche Sprache
- Deutsch

Antworte NUR als JSON-Array mit Strings."""

        scenes_text = "\n".join([f"- {s.get('title', s) if isinstance(s, dict) else s}" for s in scenes])
        user_prompt = f"""Keyword: {keyword}
Gravur-Text: {engraving_text}
Szenen:
{scenes_text}

Erstelle einen Alt-Text pro Szene (für je 2 Varianten: Nur Topf und Komplettset)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._call_ai(messages)
        if result:
            try:
                result = result.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                result = result.strip()
                data = json.loads(result)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                logger.error(f"Could not parse alt texts JSON: {result}")
        return []

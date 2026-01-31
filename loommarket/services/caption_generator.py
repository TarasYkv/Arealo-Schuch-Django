"""
Caption Generator für LoomMarket.
Erstellt plattformspezifische Captions mit KI.
"""
import logging
from typing import Dict, List, Optional
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """
    Generiert Social Media Captions mit Gemini.
    Plattformspezifisch optimiert.
    """

    # Plattform-spezifische Limits und Stile
    PLATFORM_CONFIG = {
        'instagram': {
            'max_length': 2200,
            'hashtag_count': 15,
            'style': 'freundlich, ansprechend, mit Emojis',
            'features': ['Hashtags am Ende', 'Call-to-Action', '@-Mention'],
        },
        'facebook': {
            'max_length': 500,
            'hashtag_count': 5,
            'style': 'professionell aber persönlich',
            'features': ['Frage stellen', 'Link-Vorschau optimiert'],
        },
        'linkedin': {
            'max_length': 700,
            'hashtag_count': 5,
            'style': 'professionell, Business-orientiert',
            'features': ['Branchenbezug', 'Networking-Fokus'],
        },
        'pinterest': {
            'max_length': 500,
            'hashtag_count': 10,
            'style': 'inspirierend, visuell beschreibend',
            'features': ['Keywords für Suche', 'DIY/Inspiration'],
        },
        'twitter': {
            'max_length': 280,
            'hashtag_count': 3,
            'style': 'kurz und prägnant',
            'features': ['Trending Hashtags', 'Engagement-fördend'],
        },
        'bluesky': {
            'max_length': 300,
            'hashtag_count': 3,
            'style': 'authentisch, community-fokussiert',
            'features': ['Konversation anregen'],
        },
    }

    def __init__(self, user):
        """
        Args:
            user: Django User für API-Key
        """
        self.user = user
        self._configure_genai()

    def _configure_genai(self):
        """Konfiguriert Gemini API."""
        api_key = getattr(self.user, 'gemini_api_key', None)

        if not api_key:
            # Fallback auf Settings
            api_key = getattr(settings, 'GEMINI_API_KEY', None)

        if api_key:
            genai.configure(api_key=api_key)
        else:
            logger.warning("No Gemini API key found")

    def generate_caption(
        self,
        platform: str,
        business_name: str,
        product_name: str,
        instagram_username: str = None,
        additional_context: str = None,
    ) -> Dict[str, any]:
        """
        Generiert eine Caption für eine Plattform.

        Args:
            platform: Plattform-Key (instagram, facebook, etc.)
            business_name: Name des beworbenen Unternehmens
            product_name: Name des Produkts (z.B. "Blumentopf mit Gravur")
            instagram_username: Optional für @-Mention
            additional_context: Zusätzlicher Kontext

        Returns:
            Dict mit title, caption_text, hashtags, mention_username
        """
        result = {
            'success': False,
            'title': None,
            'caption_text': None,
            'hashtags': None,
            'mention_username': instagram_username,
            'error': None,
        }

        config = self.PLATFORM_CONFIG.get(platform)
        if not config:
            result['error'] = f"Unbekannte Plattform: {platform}"
            return result

        try:
            # Prompt erstellen
            prompt = self._build_caption_prompt(
                platform=platform,
                config=config,
                business_name=business_name,
                product_name=product_name,
                instagram_username=instagram_username,
                additional_context=additional_context,
            )

            # Gemini aufrufen
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)

            if not response or not response.text:
                result['error'] = "Keine Antwort von Gemini"
                return result

            # Antwort parsen
            parsed = self._parse_caption_response(response.text, platform)
            result.update(parsed)
            result['success'] = True

            logger.info(f"Generated caption for {platform}: {business_name}")

        except Exception as e:
            result['error'] = f"Generierungsfehler: {str(e)}"
            logger.exception(f"Error generating caption: {e}")

        return result

    def generate_all_captions(
        self,
        business_name: str,
        product_name: str,
        instagram_username: str = None,
        platforms: List[str] = None,
        additional_context: str = None,
    ) -> Dict[str, Dict]:
        """
        Generiert Captions für alle (oder ausgewählte) Plattformen.

        Args:
            business_name: Name des beworbenen Unternehmens
            product_name: Name des Produkts
            instagram_username: Optional für @-Mention
            platforms: Liste der Plattformen (None = alle)
            additional_context: Zusätzlicher Kontext

        Returns:
            Dict mit Plattform-Keys und Caption-Dicts
        """
        if platforms is None:
            platforms = list(self.PLATFORM_CONFIG.keys())

        results = {}

        for platform in platforms:
            results[platform] = self.generate_caption(
                platform=platform,
                business_name=business_name,
                product_name=product_name,
                instagram_username=instagram_username,
                additional_context=additional_context,
            )

        return results

    def _build_caption_prompt(
        self,
        platform: str,
        config: Dict,
        business_name: str,
        product_name: str,
        instagram_username: str = None,
        additional_context: str = None,
    ) -> str:
        """Erstellt den Prompt für die Caption-Generierung."""

        features_text = ", ".join(config['features'])

        prompt = f"""Du bist ein Social Media Marketing-Experte. Erstelle eine {platform.capitalize()}-Caption.

DETAILS:
- Plattform: {platform.capitalize()}
- Beworbenes Unternehmen: {business_name}
- Produkt: {product_name} (personalisiertes Geschenk mit Lasergravur)
{f'- Instagram des Unternehmens: @{instagram_username}' if instagram_username else ''}
{f'- Zusätzlicher Kontext: {additional_context}' if additional_context else ''}

PLATTFORM-ANFORDERUNGEN:
- Maximale Textlänge: {config['max_length']} Zeichen
- Stil: {config['style']}
- Besonderheiten: {features_text}
- Anzahl Hashtags: {config['hashtag_count']}

AUFGABE:
Erstelle eine ansprechende Caption, die:
1. Das personalisierte Geschenk mit {business_name}-Branding bewirbt
2. Zum Engagement anregt
3. Die Marke positiv darstellt
{f'4. @{instagram_username} erwähnt' if instagram_username else ''}

WICHTIG: Verwende KEINE Emojis! Nur Text und Hashtags.

FORMAT DER ANTWORT (EXAKT einhalten):
TITEL: [Kurzer, knackiger Titel - max 100 Zeichen]
---
CAPTION:
[Die Caption hier - ohne Hashtags]
---
HASHTAGS:
[Hashtags mit # - durch Leerzeichen getrennt]

Schreibe NUR in diesem Format, keine zusätzlichen Erklärungen."""

        return prompt

    def _parse_caption_response(self, response_text: str, platform: str) -> Dict:
        """Parst die Gemini-Antwort in strukturierte Daten."""
        result = {
            'title': None,
            'caption_text': None,
            'hashtags': None,
        }

        try:
            text = response_text.strip()

            # Titel extrahieren
            if 'TITEL:' in text:
                title_start = text.find('TITEL:') + 6
                title_end = text.find('---', title_start)
                if title_end == -1:
                    title_end = text.find('\n', title_start)
                if title_end > title_start:
                    result['title'] = text[title_start:title_end].strip()

            # Caption extrahieren
            if 'CAPTION:' in text:
                caption_start = text.find('CAPTION:') + 8
                caption_end = text.find('---', caption_start)
                if caption_end == -1:
                    caption_end = text.find('HASHTAGS:', caption_start)
                if caption_end > caption_start:
                    result['caption_text'] = text[caption_start:caption_end].strip()

            # Hashtags extrahieren
            if 'HASHTAGS:' in text:
                hashtags_start = text.find('HASHTAGS:') + 9
                hashtags_text = text[hashtags_start:].strip()
                # Bis zum nächsten Abschnitt oder Ende
                hashtags_end = hashtags_text.find('---')
                if hashtags_end > -1:
                    hashtags_text = hashtags_text[:hashtags_end]
                result['hashtags'] = hashtags_text.strip()

            # Fallback: Wenn Parsing fehlschlägt, gesamten Text als Caption
            if not result['caption_text']:
                result['caption_text'] = text
                # Hashtags aus Text extrahieren
                import re
                hashtags = re.findall(r'#\w+', text)
                if hashtags:
                    result['hashtags'] = ' '.join(hashtags)
                    # Hashtags aus Caption entfernen
                    for tag in hashtags:
                        result['caption_text'] = result['caption_text'].replace(tag, '')
                    result['caption_text'] = result['caption_text'].strip()

        except Exception as e:
            logger.warning(f"Error parsing caption response: {e}")
            result['caption_text'] = response_text

        return result

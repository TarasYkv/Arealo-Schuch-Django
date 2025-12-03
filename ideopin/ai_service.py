import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class PinAIService:
    """Service für KI-gesteuerte Pin-Generierung mit OpenAI GPT"""

    def __init__(self, user):
        self.user = user
        self.api_key = user.openai_api_key
        self.model = user.preferred_openai_model or 'gpt-4o-mini'

        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_overlay_text(self, keywords: str) -> dict:
        """Generiert einen catchy, kurzen Pin-Text aus Keywords via GPT"""
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            prompt = f"""Du bist ein Experte für Pinterest Marketing. Erstelle einen kurzen, catchy Text für ein Pinterest Pin-Bild.

Keywords: {keywords}

Anforderungen:
- Maximal 6-8 Wörter
- Aufmerksamkeitsstark und klickfördernd
- Gut lesbar als Overlay auf einem Bild
- Nutze Action-Wörter oder Fragen
- Keine Hashtags, nur der reine Text

Antworte NUR mit dem Text, ohne Anführungszeichen oder Erklärungen."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest Marketing Experte."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.8
            )

            text = response.choices[0].message.content.strip()
            # Remove quotes if present
            text = text.strip('"\'')

            return {
                'success': True,
                'text': text
            }

        except Exception as e:
            logger.error(f"Error generating overlay text: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_seo_description(self, keywords: str, image_description: str) -> dict:
        """Generiert eine Pinterest-optimierte SEO-Beschreibung via GPT"""
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            prompt = f"""Du bist ein Pinterest SEO-Experte. Erstelle eine optimierte Pin-Beschreibung.

Keywords: {keywords}
Bildbeschreibung: {image_description or 'Nicht angegeben'}

Anforderungen:
- Maximal 500 Zeichen
- Beginne mit einem starken Hook
- Integriere die Keywords natürlich
- Füge 3-5 relevante Hashtags am Ende hinzu
- Call-to-Action einbauen (z.B. "Jetzt entdecken", "Mehr erfahren")
- Emotionale Ansprache
- Pinterest-SEO-optimiert (Keywords in den ersten 100 Zeichen)

Antworte NUR mit der Beschreibung, ohne zusätzliche Erklärungen."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest SEO-Experte für deutschsprachige Pins."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )

            description = response.choices[0].message.content.strip()

            # Ensure max 500 chars
            if len(description) > 500:
                description = description[:497] + '...'

            return {
                'success': True,
                'description': description
            }

        except Exception as e:
            logger.error(f"Error generating SEO description: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_text_styling(self, keywords: str, overlay_text: str, pin_format: str = '1000x1500') -> dict:
        """
        Generiert optimales Text-Styling basierend auf Keywords und Overlay-Text.

        Berücksichtigt:
        - Textlänge für optimale Schriftgröße
        - Stimmung/Thema für Farbwahl
        - Pinterest Best-Practices
        - Kontrast und Lesbarkeit
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            # Berechne Bildmaße
            width, height = map(int, pin_format.split('x'))
            text_length = len(overlay_text)

            prompt = f"""Du bist ein Pinterest Design-Experte. Erstelle ein optimales Text-Styling für einen Pinterest Pin.

Overlay-Text: "{overlay_text}"
Textlänge: {text_length} Zeichen
Keywords/Thema: {keywords}
Bildformat: {width}x{height}px

Analysiere das Thema und erstelle ein passendes, kontrastreiches Styling.

Antworte NUR im folgenden JSON-Format (keine Erklärungen):
{{
    "style_preset": "modern_bold|elegant_serif|playful_color|minimal_clean|dark_contrast|bright_fresh|vintage_retro|professional",
    "text_font": "Arial|Helvetica|Georgia|Impact|Verdana|Times New Roman",
    "text_size": <optimale Schriftgröße 24-96 basierend auf Textlänge>,
    "text_color": "<Hex-Farbe für Text>",
    "text_secondary_color": "<Hex-Farbe für Outline/Schatten>",
    "text_background_color": "<Hex-Farbe für Hintergrund oder leer>",
    "text_background_opacity": <0.0-1.0>,
    "text_effect": "none|shadow|outline|glow|frame|banner|badge",
    "text_position": "top|center|bottom",
    "text_padding": <15-40>,
    "reasoning": "<kurze Begründung für die Wahl>"
}}

Regeln:
- Kurze Texte (< 30 Zeichen): große Schrift (60-96px)
- Mittlere Texte (30-60 Zeichen): mittlere Schrift (42-60px)
- Lange Texte (> 60 Zeichen): kleinere Schrift (24-42px)
- Immer hohen Kontrast zwischen Text und Hintergrund
- Bei hellen Themen: dunkle Schrift oder Outline
- Bei dunklen Themen: helle Schrift mit Schatten
- Für Pinterest: Bold, auffällig, leicht lesbar
- Professionelle Themen: Serifenschrift, dezente Farben
- Lifestyle/Food: warme, einladende Farben
- Tech/Modern: kühle, klare Farben"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest Design-Experte. Antworte nur mit validem JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON
            import json
            # Handle markdown code blocks
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            styling = json.loads(result_text)

            # Validierung und Defaults
            valid_presets = ['custom', 'modern_bold', 'elegant_serif', 'playful_color', 'minimal_clean',
                           'dark_contrast', 'bright_fresh', 'vintage_retro', 'professional']
            valid_effects = ['none', 'shadow', 'outline', 'glow', 'frame', 'banner', 'badge']
            valid_positions = ['top', 'center', 'bottom']
            valid_fonts = ['Arial', 'Helvetica', 'Georgia', 'Impact', 'Verdana', 'Times New Roman']

            styling['style_preset'] = styling.get('style_preset', 'modern_bold')
            if styling['style_preset'] not in valid_presets:
                styling['style_preset'] = 'modern_bold'

            styling['text_effect'] = styling.get('text_effect', 'shadow')
            if styling['text_effect'] not in valid_effects:
                styling['text_effect'] = 'shadow'

            styling['text_position'] = styling.get('text_position', 'center')
            if styling['text_position'] not in valid_positions:
                styling['text_position'] = 'center'

            styling['text_font'] = styling.get('text_font', 'Arial')
            if styling['text_font'] not in valid_fonts:
                styling['text_font'] = 'Arial'

            # Numerische Werte validieren
            styling['text_size'] = max(24, min(96, int(styling.get('text_size', 48))))
            styling['text_padding'] = max(10, min(50, int(styling.get('text_padding', 20))))
            styling['text_background_opacity'] = max(0.0, min(1.0, float(styling.get('text_background_opacity', 0.7))))

            # Hex-Farben validieren
            for color_field in ['text_color', 'text_secondary_color', 'text_background_color']:
                color = styling.get(color_field, '')
                if color and not color.startswith('#'):
                    color = '#' + color
                if color and len(color) != 7:
                    color = '#FFFFFF' if color_field == 'text_color' else '#000000'
                styling[color_field] = color

            return {
                'success': True,
                'styling': styling,
                'reasoning': styling.get('reasoning', '')
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in styling generation: {e}")
            # Fallback: Return safe defaults
            return self._get_fallback_styling(overlay_text)
        except Exception as e:
            logger.error(f"Error generating text styling: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_fallback_styling(self, overlay_text: str) -> dict:
        """Fallback-Styling wenn KI-Generierung fehlschlägt"""
        text_length = len(overlay_text)

        # Schriftgröße basierend auf Textlänge
        if text_length < 30:
            text_size = 72
        elif text_length < 60:
            text_size = 54
        else:
            text_size = 36

        return {
            'success': True,
            'styling': {
                'style_preset': 'modern_bold',
                'text_font': 'Arial',
                'text_size': text_size,
                'text_color': '#FFFFFF',
                'text_secondary_color': '#000000',
                'text_background_color': '#000000',
                'text_background_opacity': 0.6,
                'text_effect': 'shadow',
                'text_position': 'center',
                'text_padding': 25,
            },
            'reasoning': 'Fallback-Styling (kontrastreiche Standard-Einstellungen)',
            'is_fallback': True
        }

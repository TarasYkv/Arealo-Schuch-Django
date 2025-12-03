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

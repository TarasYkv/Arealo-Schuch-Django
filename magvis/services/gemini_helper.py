"""Gemini-Helper für magvis: Diagramm + Brainstorming-Bilder.

Dünne Fassade über ideopin.gemini_service.GeminiImageService.
Modell hartkodiert auf gemini-2.5-flash-image (günstigstes Bildmodell).
"""
import base64
import logging
import os
import uuid

from django.conf import settings as django_settings

logger = logging.getLogger(__name__)


class MagvisGeminiHelper:
    DEFAULT_MODEL = 'gemini-2.5-flash-image'

    def __init__(self, user, magvis_settings=None):
        self.user = user
        self.model = (magvis_settings.gemini_image_model
                      if magvis_settings and magvis_settings.gemini_image_model
                      else self.DEFAULT_MODEL)
        self._service = None

    @property
    def service(self):
        if self._service is None:
            from ideopin.gemini_service import GeminiImageService
            api_key = getattr(self.user, 'gemini_api_key', None) or getattr(self.user, 'google_api_key', None)
            if not api_key:
                raise RuntimeError(
                    'Gemini API-Key fehlt. Bitte unter /accounts/api-einstellungen/ "gemini_api_key" setzen.'
                )
            self._service = GeminiImageService(api_key=api_key)
        return self._service

    def generate_title_image(self, topic: str, summary: str = '') -> dict:
        """Erzeugt das Hero-Titelbild des Blogs. Mit Retry bei Text-Response."""
        prompts = [
            # 1. Versuch: ausfuehrlicher Prompt
            (
                f'IMAGE GENERATION ONLY — DO NOT WRITE TEXT. Generate a wide '
                f'lifestyle hero photo for a German blog about "{topic}". '
                f'Theme: thoughtfully personal handmade gift moment.\n\n'
                f'Composition: editorial blog header, real photograph aesthetic. '
                f'{summary}\n\n'
                f'Style: warm natural light, soft earth-tone palette (sage, beige, '
                f'cream, terracotta), shallow depth of field, magazine photo. '
                f'No text on image, no watermark, no logos.\n\n'
                f'OUTPUT MUST BE A PHOTO. NO TEXT IN RESPONSE.'
            ),
            # 2. Versuch: kuerzer + direkter
            (
                f'Photograph: a beautifully arranged personal handmade gift '
                f'related to "{topic}". Editorial lifestyle composition, soft '
                f'natural light, earth tones, shallow depth of field. '
                f'No text or logos in the image. Generate a photo, do not write text.'
            ),
            # 3. Versuch: minimal
            (
                f'Lifestyle photo, gift theme: {topic}. Soft warm light. '
                f'Earth tones. Shallow depth of field. No text in image. '
                f'IMAGE OUTPUT ONLY.'
            ),
        ]
        for attempt, prompt in enumerate(prompts, start=1):
            result = self._generate_and_save(prompt, prefix='title')
            if result.get('success'):
                if attempt > 1:
                    logger.info('Title-image succeeded on attempt %d', attempt)
                return result
            logger.warning('Title-image attempt %d failed: %s', attempt, result.get('error', '?'))
        return {'success': False, 'error': 'all 3 attempts failed'}

    def generate_diagram(self, topic: str, content_summary: str = '') -> dict:
        """Erzeugt ein Infografik-/Diagramm-Bild für den Blog (Bar-Chart, Flow oder Mindmap-Style)."""
        prompt = (
            f'Generate an image (NOT TEXT, IMAGE only) — a clean modern German infographic about "{topic}".\n\n'
            f'Style: minimalist flat design, soft earth-tone palette (beige, sage green, warm brown), '
            f'clear sans-serif typography in German, lots of whitespace.\n\n'
            f'Content: {content_summary or "the most important key points about the topic"} — '
            f'visualized as 3 to 5 key points, each with a simple icon and a German one-line caption.\n\n'
            f'STRICT NEGATIVES: no photorealism, no real people, no stock-photo look, no English text.\n\n'
            f'Output: ONLY the image. Do not respond with text.'
        )
        return self._generate_and_save(prompt, prefix='diagram')

    def generate_brainstorm(self, topic: str) -> dict:
        """Brainstorming-Bild: visuelle Mindmap / Concept-Board."""
        prompt = (
            f'Generate an image (NOT TEXT, IMAGE only) — a hand-drawn brainstorming mind-map about "{topic}".\n\n'
            f'Visual style: pencil + watercolor accents on cream-colored paper, earth-tone palette '
            f'(beige, sage green, warm brown). The central topic is written in the middle as a hand-drawn '
            f'bubble. Around it, 5-7 connected branches lead to sub-topics, each labelled in German handwriting '
            f'with a small doodle icon (heart, gift, plant, candle, hand, etc.).\n\n'
            f'Composition: square format. Whitespace around. Looks like a real notebook page.\n\n'
            f'STRICT NEGATIVES: no photographic content, no real people, no realistic objects, '
            f'no text descriptions outside the image, no English labels.\n\n'
            f'Output: ONLY the image. Do not respond with text.'
        )
        return self._generate_and_save(prompt, prefix='brainstorm')

    def _generate_and_save(self, prompt: str, prefix: str) -> dict:
        """Ruft Gemini, speichert Bild in MEDIA_ROOT/magvis/blog_images/, liefert dict."""
        # Titelbild querformat (16:9), Diagramm/Brainstorm quadratisch
        if prefix == 'title':
            width, height = 1280, 720
        else:
            width, height = 1024, 1024
        try:
            result = self.service.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                model=self.model,
            )
        except Exception as exc:
            logger.exception('Gemini-Bildgenerierung fehlgeschlagen')
            return {'success': False, 'error': str(exc)}

        if not result.get('success') or not result.get('image_data'):
            return {'success': False, 'error': result.get('error', 'Unbekannter Gemini-Fehler')}

        rel_dir = os.path.join('magvis', 'blog_images')
        abs_dir = os.path.join(django_settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        filename = f'{prefix}_{uuid.uuid4().hex[:12]}.png'
        rel_path = os.path.join(rel_dir, filename)
        abs_path = os.path.join(django_settings.MEDIA_ROOT, rel_path)

        try:
            with open(abs_path, 'wb') as fh:
                fh.write(base64.b64decode(result['image_data']))
        except Exception as exc:
            logger.exception('Bild speichern fehlgeschlagen')
            return {'success': False, 'error': f'Save-Fehler: {exc}'}

        return {
            'success': True,
            'rel_path': rel_path.replace('\\', '/'),
            'abs_path': abs_path,
            'url': django_settings.MEDIA_URL + rel_path.replace('\\', '/'),
        }

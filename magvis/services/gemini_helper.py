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

    def generate_diagram(self, topic: str, content_summary: str = '') -> dict:
        """Erzeugt ein Infografik-/Diagramm-Bild für den Blog (Bar-Chart, Flow oder Mindmap-Style)."""
        prompt = (
            f'Erstelle eine moderne, klare Infografik zum Thema "{topic}". '
            f'Stil: minimalistisch, sanfte Erdtöne (Beige, Salbeigrün, warmes Braun), '
            f'klare Typografie auf Deutsch, übersichtliches Layout. '
            f'Inhaltlich: {content_summary or "die wichtigsten Punkte des Themas"} '
            f'als gut verständliche Visualisierung (z.B. drei bis fünf Schlüssel-Punkte mit Icons). '
            f'KEINE Fotorealismus, KEINE menschlichen Figuren, KEIN Stockfoto-Look. '
            f'Quadratisches Format. Hochauflösend.'
        )
        return self._generate_and_save(prompt, prefix='diagram')

    def generate_brainstorm(self, topic: str) -> dict:
        """Brainstorming-Bild: visuelle Mindmap / Concept-Board."""
        prompt = (
            f'Brainstorming-Mindmap zum Thema "{topic}". '
            f'Stil: handgezeichnete Skizze auf cremefarbenem Papier, leichte Aquarell-Akzente in Erdtönen. '
            f'Zentraler Begriff in der Mitte, drumherum 5-7 verzweigte Unterthemen mit kleinen Icons/Symbolen, '
            f'verbindende Linien. Deutsch beschriftet. Locker und kreativ wirkend, '
            f'wie aus einem Notizbuch. KEINE Fotos, KEINE Personen. Quadratisches Format.'
        )
        return self._generate_and_save(prompt, prefix='brainstorm')

    def _generate_and_save(self, prompt: str, prefix: str) -> dict:
        """Ruft Gemini, speichert Bild in MEDIA_ROOT/magvis/blog_images/, liefert dict."""
        try:
            result = self.service.generate_image(
                prompt=prompt,
                width=1024,
                height=1024,
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

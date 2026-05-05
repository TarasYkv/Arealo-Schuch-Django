"""Magvis Image-Post-Pipeline (ideopin-Stil).

Pro Bild einzeln entscheiden:
- mit/ohne Text-Overlay (PIL oder Gemini)
- Auto-Titel + Auto-Beschreibung via GLM-5.1
- Posten via Upload-Post.com auf gewählte Plattformen
"""
from __future__ import annotations

import io
import logging
import os
import uuid

import requests
from django.conf import settings as django_settings

from ..models import MagvisImageAsset
from .llm_client import MagvisLLMClient
from .gemini_helper import MagvisGeminiHelper

logger = logging.getLogger(__name__)

UPLOAD_POST_PHOTO_URL = 'https://api.upload-post.com/api/upload_photos'


class MagvisImagePostPipeline:
    def __init__(self, asset: MagvisImageAsset):
        self.asset = asset
        self.project = asset.project
        self.user = asset.project.user

        from ..models import MagvisSettings
        self.settings, _ = MagvisSettings.objects.get_or_create(user=self.user)

    # --- public ---------------------------------------------------------------

    def post(self, *, platforms: list[str], use_overlay: bool = False,
             overlay_text: str = '', overlay_method: str = 'pil',
             title: str | None = None, description: str | None = None) -> dict:
        """Verarbeitet das Bild (Overlay) und postet auf alle gewählten Plattformen."""
        # 1. Auto-Texte falls fehlen
        captions = self._generate_captions(platforms) if (not title or not description) else {}
        title = title or captions.get('title', '')
        description = description or captions.get('description', '')

        self.asset.title_de = title or self.asset.title_de
        self.asset.description_de = description or self.asset.description_de
        self.asset.target_platforms = platforms
        self.asset.use_overlay = use_overlay
        self.asset.overlay_text = overlay_text or ''
        self.asset.overlay_method = overlay_method
        self.asset.save()

        # 2. Overlay anwenden
        image_path = self.asset.effective_path
        if use_overlay and overlay_text:
            try:
                if overlay_method == 'gemini':
                    image_path = self._apply_gemini_overlay(overlay_text)
                else:
                    image_path = self._apply_pil_overlay(overlay_text)
                self.asset.processed_path = image_path
                self.asset.save(update_fields=['processed_path'])
            except Exception as exc:
                logger.warning('Overlay failed: %s — Posting Original', exc)
                image_path = self.asset.src_path

        # 3. Post via Upload-Post
        result = self._post_to_uploadpost(image_path, title, description, platforms, captions)
        # Merge mit bisherigem posted_status — Re-Runs für andere Plattformen
        # dürfen vorherige Erfolge nicht löschen (Idempotenz).
        merged = dict(self.asset.posted_status or {})
        merged.update(result.get('per_platform', {}) or {})
        self.asset.posted_status = merged
        if result.get('request_id'):
            self.asset.upload_post_request_id = result['request_id']
        self.asset.save(update_fields=['posted_status', 'upload_post_request_id'])
        return result

    # --- helpers --------------------------------------------------------------

    def _generate_captions(self, platforms: list[str] | None = None) -> dict:
        """Erzeugt plattform-spezifische Captions in einem GLM-Call.

        Liefert Dict mit:
          - title: kurzer Hook-Titel (≤100)
          - description: Universal-Fallback (≤500), in Pinterest-Stil
          - instagram_caption: Story-driven, 800-1500 Zeichen, Hashtags
          - pinterest_caption: Keyword-rich, ≤500, search-optimiert
          - tiktok_caption: punchig, ≤2200, Hashtags
          - facebook_caption: wie Instagram (etwas kürzer ok)
          - threads_caption: ≤500, knapp und persönlich
        """
        platforms = platforms or []
        blog = getattr(self.project, 'blog', None)
        blog_url = (blog.shopify_published_url if blog else '') or 'https://naturmacher.de/'
        topic = self.project.topic or self.project.title or ''
        image_kind = self.asset.get_source_display() if hasattr(self.asset, 'get_source_display') else self.asset.source
        bild_kontext = self.asset.title_de or image_kind

        prompt = (
            f'Erzeuge Social-Media-Captions für ein Bild von Naturmacher.de '
            f'(personalisierte Blumentöpfe mit Lasergravur als Geschenk, Familienbetrieb '
            f'aus Bensheim, handgefertigt in Deutschland).\n\n'
            f'Thema des Posts: "{topic}"\n'
            f'Blog-/Ziel-URL: {blog_url}\n'
            f'Bild-Kontext: {bild_kontext}\n\n'
            f'Marken-Voice:\n'
            f'- Du-Form, herzlich, persönlich, naturverbunden\n'
            f'- Niemals "verkaufen", "Sonderangebot", "Rabatt"\n'
            f'- Emotional, nicht werblich\n\n'
            f'Erzeuge folgende Felder als JSON:\n\n'
            f'1. **title** (max 90 Zeichen): hookiger Kurztitel, neugierig machend, '
            f'   ohne Hashtags. Beispiel: "Ein Geschenk, das ihn wirklich berührt 💚"\n\n'
            f'2. **instagram_caption** (800-1500 Zeichen):\n'
            f'   - Zeile 1: Hook, max 90 Zeichen, weckt Neugier\n'
            f'   - Leerzeile, dann 3-5 Sätze emotionale Story / Mehrwert\n'
            f'   - Konkreter CTA "👉 Mehr im Link in Bio" (eigene Zeile)\n'
            f'   - Leerzeile\n'
            f'   - 8-10 deutsche Hashtags (Mix aus Brand, thematisch, generisch '
            f'   #Geschenkidee, #PersonalisiertesGeschenk, #NaturmacherDe, #HandmadeInGermany etc.)\n'
            f'   - Sparsame Emojis (max 2-3 in der Mitte des Textes, nicht am Anfang)\n\n'
            f'3. **pinterest_caption** (max 480 Zeichen): KEYWORD-OPTIMIERT für Pinterest-Suche.\n'
            f'   - Erste 100 Zeichen sind die wichtigsten Keywords\n'
            f'   - Suchbegriffe natürlich einbauen: "personalisiertes Geschenk", '
            f'   "Geschenk mit Gravur", "[Thema]-Geschenk", "DIY Geschenkidee"\n'
            f'   - Klare Beschreibung was zu sehen ist + warum klicken\n'
            f'   - 3-5 Hashtags am Ende reichen (Pinterest-Algorithmus mag Keywords mehr als Hashtags)\n'
            f'   - Du-Form, aber sachlicher als Instagram\n\n'
            f'4. **tiktok_caption** (300-800 Zeichen): punchig, jung, mit 5-8 Hashtags. '
            f'   Trend-Vokabular ok ("POV:", "Storytime:"). 2-3 Emojis.\n\n'
            f'5. **threads_caption** (max 480 Zeichen): kurzer persönlicher Gedanke '
            f'   im Tagebuch-Stil, 1-2 Hashtags am Ende.\n\n'
            f'6. **description** (max 480 Zeichen): generischer Fallback im Pinterest-Stil '
            f'   (keyword-haltig). Wird genutzt wenn keine plattform-spezifische Caption greift.\n\n'
            f'WICHTIG: Niemals den Topic 1:1 als ganzen Caption zurückgeben. '
            f'Niemals nur die URL als Caption. Immer eine echte, ausformulierte Story.\n\n'
            f'Antworte ausschließlich als gültiges JSON mit allen 6 Feldern.'
        )
        try:
            glm = MagvisLLMClient(self.user, self.settings)
        except Exception as exc:
            logger.warning('GLM-Init für Captions: %s', exc)
            return self._fallback_captions(topic)
        # 6 Felder × bis zu 1500 Zeichen → Token-Budget grosszuegig.
        # json_chat (ohne max_tokens) wurde vom Provider-Default abgeschnitten,
        # JSON kam unvollstaendig zurueck → Parser failed → Fallback.
        try:
            data = glm.json_chat_with_retry(
                prompt, expect='object', max_tokens=4096, retries=3,
            )
            if isinstance(data, dict) and (data.get('description') or data.get('instagram_caption')):
                ig_cap = str(data.get('instagram_caption', ''))[:2000]
                pin_cap = str(data.get('pinterest_caption', ''))[:500]
                return {
                    'title': str(data.get('title', ''))[:100],
                    'description': str(data.get('description') or pin_cap)[:500],
                    'instagram_caption': ig_cap,
                    'pinterest_caption': pin_cap,
                    'tiktok_caption': str(data.get('tiktok_caption', ''))[:2200],
                    'facebook_caption': str(
                        data.get('facebook_caption') or data.get('instagram_caption', '')
                    )[:2000],
                    'threads_caption': str(data.get('threads_caption', ''))[:500],
                }
        except Exception as exc:
            logger.warning('GLM-Captions: %s', exc)
        logger.warning('GLM-Captions: kein gueltiges JSON nach Retries — Fallback aktiv')
        return self._fallback_captions(topic)

    def _fallback_captions(self, topic: str) -> dict:
        """Fallback der weniger schlimm ist als nur Topic[:200]."""
        topic_clean = (topic or 'Personalisierte Geschenkidee').strip()
        ig = (
            f'{topic_clean} – persönlich, mit Liebe handgefertigt. ✨\n\n'
            f'Manchmal sind die schönsten Geschenke nicht die teuersten, '
            f'sondern die, die wirklich zeigen: "Ich habe an dich gedacht."\n'
            f'Bei uns wird jeder Blumentopf in Bensheim einzeln graviert – '
            f'mit deinem Namen, einem Datum oder einem Spruch, der bleibt.\n\n'
            f'👉 Mehr Geschenkideen findest du im Link in Bio.\n\n'
            f'#Geschenkidee #PersonalisiertesGeschenk #NaturmacherDe '
            f'#HandmadeInGermany #GeschenkMitGravur #KleinesGeschenkGrosseWirkung '
            f'#EmotionaleGeschenke #FromGermany'
        )
        pin = (
            f'{topic_clean} | Personalisiertes Geschenk mit Gravur. '
            f'Handgefertigte Blumentöpfe von Naturmacher.de – die persönliche '
            f'Geschenkidee für besondere Menschen. Mit Namen, Datum oder '
            f'Wunschspruch. Made in Germany. '
            f'#Geschenkidee #PersonalisiertesGeschenk #Geschenkinspiration'
        )
        return {
            'title': f'Geschenkidee: {topic_clean}'[:100],
            'description': pin[:500],
            'instagram_caption': ig[:2000],
            'pinterest_caption': pin[:500],
            'tiktok_caption': ig[:2200],
            'facebook_caption': ig[:2000],
            'threads_caption': pin[:500],
        }

    def _apply_pil_overlay(self, text: str) -> str:
        """Schreibt Text mit Pillow auf das Bild und speichert es."""
        from ideopin.image_processor import PinImageProcessor

        src = self.asset.src_path
        if not os.path.isabs(src):
            src = os.path.join(django_settings.MEDIA_ROOT, src)

        processor = PinImageProcessor(src)
        out_image = processor.add_text_overlay(
            text=text, font='Arial', size=72, color='#FFFFFF',
            position='center', background_color='#000000', background_opacity=0.5,
        )
        rel_dir = os.path.join('magvis', 'overlays', str(self.project.id))
        abs_dir = os.path.join(django_settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f'overlay_{uuid.uuid4().hex[:10]}.png'
        rel_path = os.path.join(rel_dir, filename).replace('\\', '/')
        abs_path = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        out_image.save(abs_path, 'PNG')
        return rel_path

    def _apply_gemini_overlay(self, text: str) -> str:
        """Lässt Gemini den Text in das Bild integrieren."""
        from ideopin.gemini_service import GeminiImageService

        api_key = getattr(self.user, 'gemini_api_key', None)
        if not api_key:
            raise RuntimeError('gemini_api_key fehlt')

        svc = GeminiImageService(api_key=api_key)
        prompt = svc.build_prompt_for_text_overlay(
            text=text, background_description='', style='REALISTIC',
        ) if hasattr(svc, 'build_prompt_for_text_overlay') else (
            f'Schreibe den Text "{text}" prominent in das beigefügte Bild. '
            f'Stil: elegant, gut lesbar, harmonische Integration. Quadratisches Format.'
        )

        src = self.asset.src_path
        if not os.path.isabs(src):
            src = os.path.join(django_settings.MEDIA_ROOT, src)

        result = svc.generate_image(
            prompt=prompt, reference_image=src, width=1024, height=1024,
            model=self.settings.gemini_image_model,
        )
        if not result.get('success') or not result.get('image_data'):
            raise RuntimeError(f'Gemini-Overlay-Fehler: {result.get("error")}')

        import base64
        rel_dir = os.path.join('magvis', 'overlays', str(self.project.id))
        abs_dir = os.path.join(django_settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f'gemini_overlay_{uuid.uuid4().hex[:10]}.png'
        rel_path = os.path.join(rel_dir, filename).replace('\\', '/')
        abs_path = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        with open(abs_path, 'wb') as fh:
            fh.write(base64.b64decode(result['image_data']))
        return rel_path

    def _post_to_uploadpost(self, image_path: str, title: str, description: str,
                            platforms: list[str], captions: dict | None = None) -> dict:
        """Post-Wrapper: SPLIT pro Plattform (statt 1 Bundle-Request) damit
        ein Pinterest-429 nicht Facebook/Instagram mitreißt. Aggregiert
        Per-Platform-Ergebnisse zu einem result-Dict."""
        if not platforms:
            return {'success': False, 'error': 'keine Plattformen', 'per_platform': {}}

        captions = captions or {}

        # Kein Split nötig wenn nur 1 Plattform
        if len(platforms) == 1:
            return self._post_single_platform(image_path, title, description, platforms, captions)

        # SPLIT: pro Plattform ein Request — Fail-Isolation
        agg_per_platform = {}
        any_success = False
        request_ids = []
        for plat in platforms:
            r = self._post_single_platform(image_path, title, description, [plat], captions)
            agg_per_platform.update(r.get('per_platform') or {})
            if r.get('success'):
                any_success = True
            if r.get('request_id'):
                request_ids.append(str(r['request_id']))
        return {
            'success': any_success,
            'request_id': ','.join(request_ids),
            'per_platform': agg_per_platform,
        }

    def _post_single_platform(self, image_path: str, title: str, description: str,
                               platforms: list[str], captions: dict | None = None) -> dict:
        api_key = (getattr(self.user, 'upload_post_api_key', None)
                   or getattr(self.user, 'uploadpost_api_key', None))
        upload_user = self.settings.upload_post_user or getattr(self.user, 'upload_post_user_id', '')
        if not api_key or not upload_user:
            return {'success': False, 'error': 'Upload-Post API-Key/User fehlt',
                    'per_platform': {p: {'success': False, 'error': 'Config'} for p in platforms}}

        # src_path kann sein: lokal-relative Pfad / lokal-absoluter Pfad /
        # HTTPS-URL (z.B. Shopify-CDN bei Blog-Diagramm/Brainstorm).
        image_bytes = None
        if image_path and image_path.startswith(('http://', 'https://')):
            try:
                image_bytes = requests.get(image_path, timeout=60).content
            except Exception as exc:
                return {'success': False, 'error': f'Bild-URL nicht ladbar: {exc}',
                        'per_platform': {p: {'success': False, 'error': 'URL fetch'} for p in platforms}}
        else:
            if image_path and not os.path.isabs(image_path):
                image_path = os.path.join(django_settings.MEDIA_ROOT, image_path)
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as fh:
                    image_bytes = fh.read()
            elif getattr(self.asset, 'src_url', ''):
                try:
                    image_bytes = requests.get(self.asset.src_url, timeout=60).content
                except Exception as exc:
                    return {'success': False, 'error': f'CDN-Bild nicht ladbar: {exc}',
                            'per_platform': {p: {'success': False, 'error': 'Image fetch'} for p in platforms}}
        if not image_bytes:
            return {'success': False, 'error': 'Kein Bild-Pfad/URL'}

        captions = captions or {}
        ig_text = captions.get('instagram_caption') or description or ''
        pin_text = captions.get('pinterest_caption') or description or ''
        tt_text = captions.get('tiktok_caption') or description or ''
        fb_text = captions.get('facebook_caption') or ig_text
        th_text = captions.get('threads_caption') or pin_text or description or ''

        form_data = [
            ('user', upload_user),
            ('title', (title or '')[:100]),
        ]
        for plat in platforms:
            form_data.append(('platform[]', plat))

        # Pinterest braucht eigene Felder + zwingend pinterest_link UND board_id
        if 'pinterest' in platforms:
            form_data.append(('pinterest_title', (title or '')[:100]))
            form_data.append(('pinterest_description', pin_text[:500]))
            # pinterest_link ist Pflicht — Ziel-URL die der Pin oeffnet.
            project = getattr(self.asset, 'project', None)
            blog_url = ''
            if project and hasattr(project, 'blog'):
                blog_url = project.blog.shopify_published_url or ''
            pin_link = blog_url or 'https://naturmacher.de/'
            form_data.append(('pinterest_link', pin_link))
            # Pinterest-Board-ID — zwingend.
            # Aus MagvisSettings.pinterest_board_id oder hardcoded Default
            # ('Personalisierte Geschenkideen' Board ID — passt thematisch).
            board_id = (getattr(self.settings, 'pinterest_board_id', '') or
                        '1042372344944413125')  # 'Personalisierte Geschenkideen'
            form_data.append(('pinterest_board_id', board_id))

        # Plattform-spezifische Captions — Upload-Post nutzt pro Plattform
        # eigene Field-Namen, sonst Fallback auf top-level description.
        if 'instagram' in platforms:
            form_data.append(('instagram_caption', ig_text[:2000]))
        if 'facebook' in platforms:
            form_data.append(('facebook_caption', fb_text[:2000]))
        if 'threads' in platforms:
            form_data.append(('threads_caption', th_text[:500]))
        if 'tiktok' in platforms:
            form_data.append(('tiktok_caption', tt_text[:2200]))
        # Top-level description als universeller Fallback
        form_data.append(('description', (description or pin_text or '')[:500]))

        # Upload-Post nutzt das Field 'photos[]' (Plural mit eckigen Klammern)
        files = {'photos[]': (f'magvis_{self.asset.id}.png', io.BytesIO(image_bytes), 'image/png')}
        headers = {'Authorization': f'Apikey {api_key.strip()}'}

        try:
            resp = requests.post(UPLOAD_POST_PHOTO_URL, headers=headers,
                                 data=form_data, files=files, timeout=180)
            resp.raise_for_status()
            data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {'raw': resp.text}
        except requests.RequestException as exc:
            logger.exception('Upload-Post Photo')
            return {'success': False, 'error': str(exc),
                    'per_platform': {p: {'success': False, 'error': str(exc)} for p in platforms}}

        per_platform = {}
        # Upload-Post liefert je nach Antwort entweder per_platform-Dict oder Pauschal-Status
        platform_results = data.get('results') or data.get('platforms') or {}
        for plat in platforms:
            r = platform_results.get(plat, {}) if isinstance(platform_results, dict) else {}
            per_platform[plat] = {
                'success': bool(r.get('success', True)),
                'url': r.get('url') or r.get('post_url') or '',
                'error': r.get('error', ''),
            }

        return {
            'success': True,
            'request_id': data.get('request_id') or data.get('id', ''),
            'per_platform': per_platform,
            'data': data,
        }

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
        if not title or not description:
            auto = self._generate_title_description()
            title = title or auto.get('title', '')
            description = description or auto.get('description', '')

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
        result = self._post_to_uploadpost(image_path, title, description, platforms)
        self.asset.posted_status = result.get('per_platform', {})
        if result.get('request_id'):
            self.asset.upload_post_request_id = result['request_id']
        self.asset.save(update_fields=['posted_status', 'upload_post_request_id'])
        return result

    # --- helpers --------------------------------------------------------------

    def _generate_title_description(self) -> dict:
        glm = MagvisLLMClient(self.user, self.settings)
        prompt = (
            f"Erstelle für ein Social-Media-Bild zum Thema \"{self.project.topic}\" "
            f"einen kurzen Titel (max. 60 Zeichen) und eine knackige Beschreibung "
            f"(max. 200 Zeichen) auf Deutsch. Bild-Kontext: {self.asset.title_de or self.asset.source}.\n\n"
            f'Antworte als JSON: {{"title": "...", "description": "..."}}'
        )
        try:
            data = glm.json_chat(prompt)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning('GLM-Title-Description: %s', exc)
            return {'title': self.project.topic[:60], 'description': self.project.topic[:200]}

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
                            platforms: list[str]) -> dict:
        api_key = (getattr(self.user, 'upload_post_api_key', None)
                   or getattr(self.user, 'uploadpost_api_key', None))
        upload_user = self.settings.upload_post_user or getattr(self.user, 'upload_post_user_id', '')
        if not api_key or not upload_user:
            return {'success': False, 'error': 'Upload-Post API-Key/User fehlt',
                    'per_platform': {p: {'success': False, 'error': 'Config'} for p in platforms}}

        if image_path and not os.path.isabs(image_path):
            image_path = os.path.join(django_settings.MEDIA_ROOT, image_path)

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as fh:
                image_bytes = fh.read()
        elif self.asset.src_url:
            try:
                image_bytes = requests.get(self.asset.src_url, timeout=60).content
            except Exception as exc:
                return {'success': False, 'error': f'CDN-Bild nicht ladbar: {exc}',
                        'per_platform': {p: {'success': False, 'error': 'Image fetch'} for p in platforms}}
        else:
            return {'success': False, 'error': 'Kein Bild-Pfad/URL'}

        form_data = [
            ('user', upload_user),
            ('title', (title or '')[:100]),
            ('description', (description or '')[:500]),
        ]
        for plat in platforms:
            form_data.append(('platform[]', plat))

        files = {'photo[]': (f'magvis_{self.asset.id}.png', io.BytesIO(image_bytes), 'image/png')}
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

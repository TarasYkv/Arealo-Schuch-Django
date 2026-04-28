"""Magvis Social-Pipeline: Postet Video über Upload-Post.com.

Nutzt die User-Konfiguration upload-post-Logik wie in videos/views.py:api_post_to_social,
fokussiert auf YouTube-Posting (für Blog-Embed) plus optional weitere Plattformen.
Nach erfolgreichem Post: extrahiert YouTube-URL und schreibt project.youtube_video_id.
"""
from __future__ import annotations

import io
import logging
import time

import requests

from ..models import MagvisProject
from .youtube_embed import extract_video_id

logger = logging.getLogger(__name__)

UPLOAD_POST_VIDEO_URL = 'https://api.upload-post.com/api/upload'
UPLOAD_POST_PHOTO_URL = 'https://api.upload-post.com/api/upload_photos'


class MagvisSocialPipeline:
    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)

    def post_video(self, platforms: list[str] | None = None,
                   title: str | None = None, description: str | None = None) -> dict:
        """Postet das Video über Upload-Post."""
        if not self.project.posted_video:
            return {'success': False, 'error': 'Kein Video zum Posten verknüpft'}

        api_key = getattr(self.user, 'upload_post_api_key', None) or getattr(self.user, 'uploadpost_api_key', None)
        upload_user = self.magvis_settings.upload_post_user or getattr(self.user, 'upload_post_user_id', '')
        if not api_key or not upload_user:
            return {
                'success': False,
                'error': 'Upload-Post API-Key oder User-ID fehlt. Bitte in /accounts/api-einstellungen/ und /magvis/einstellungen/ konfigurieren.',
            }

        platforms = platforms or self.magvis_settings.default_image_platforms or ['youtube']
        if 'youtube' not in platforms:
            platforms = list(platforms) + ['youtube']  # YouTube für Embed zwingend

        video = self.project.posted_video
        if not video.video_file:
            return {'success': False, 'error': 'Video-Datei fehlt'}

        title = title or video.title or self.project.title
        description = description or video.description or f'Magvis-Video zum Thema "{self.project.topic}"'

        try:
            video.video_file.open('rb')
            video_bytes = video.video_file.read()
            video.video_file.close()
        except Exception as exc:
            return {'success': False, 'error': f'Video-Datei nicht lesbar: {exc}'}

        form_data = [
            ('user', upload_user),
            ('title', title[:100]),
            ('description', description[:500]),
        ]
        for plat in platforms:
            form_data.append(('platform[]', plat))

        files = {'video': (video.video_file.name.split('/')[-1], io.BytesIO(video_bytes), 'video/mp4')}
        headers = {'Authorization': f'Apikey {api_key.strip()}'}

        try:
            resp = requests.post(UPLOAD_POST_VIDEO_URL, headers=headers, data=form_data, files=files, timeout=300)
            resp.raise_for_status()
            data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {'raw': resp.text}
        except requests.RequestException as exc:
            logger.exception('Upload-Post fehlgeschlagen')
            return {'success': False, 'error': f'Upload-Post-Fehler: {exc}'}

        request_id = data.get('request_id') or data.get('id') or ''
        video.social_request_id = request_id
        video.social_platforms_posted = ','.join(platforms)
        video.save(update_fields=['social_request_id', 'social_platforms_posted'])

        return {'success': True, 'request_id': request_id, 'data': data}

    def poll_youtube_url(self, max_wait_s: int = 600, interval_s: int = 15) -> dict:
        """Pollt Upload-Post-Status bis YouTube-URL verfügbar oder Timeout."""
        api_key = getattr(self.user, 'upload_post_api_key', None) or getattr(self.user, 'uploadpost_api_key', None)
        if not api_key or not self.project.posted_video or not self.project.posted_video.social_request_id:
            return {'success': False, 'error': 'Status-Polling unmöglich (Key/RequestID fehlt)'}

        deadline = time.time() + max_wait_s
        last_data = None
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f'https://api.upload-post.com/api/status/{self.project.posted_video.social_request_id}',
                    headers={'Authorization': f'Apikey {api_key.strip()}'},
                    timeout=30,
                )
                resp.raise_for_status()
                last_data = resp.json()
            except Exception as exc:
                logger.warning('Polling-Fehler: %s', exc)
                time.sleep(interval_s)
                continue

            posted_urls = (last_data or {}).get('posted_urls') or (last_data or {}).get('urls') or {}
            yt_url = (posted_urls.get('youtube')
                      if isinstance(posted_urls, dict) else None)
            if yt_url:
                video_id = extract_video_id(yt_url)
                self.project.youtube_url = yt_url
                self.project.youtube_video_id = video_id or ''
                self.project.save(update_fields=['youtube_url', 'youtube_video_id', 'updated_at'])
                video = self.project.posted_video
                video.social_posted_urls = posted_urls
                video.save(update_fields=['social_posted_urls'])
                return {'success': True, 'youtube_url': yt_url, 'video_id': video_id}

            time.sleep(interval_s)

        return {'success': False, 'error': 'Timeout beim Warten auf YouTube-URL', 'last_data': last_data}

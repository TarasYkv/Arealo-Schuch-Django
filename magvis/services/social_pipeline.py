"""Magvis Social-Pipeline: Postet Video über Upload-Post.com.

Nutzt die User-Konfiguration upload-post-Logik wie in videos/views.py:api_post_to_social,
fokussiert auf YouTube-Posting (für Blog-Embed) plus optional weitere Plattformen.
Nach erfolgreichem Post: extrahiert YouTube-URL und schreibt project.youtube_video_id.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import struct
import subprocess
import tempfile
import time

import requests

from ..models import MagvisProject
from .youtube_embed import extract_video_id

logger = logging.getLogger(__name__)

UPLOAD_POST_VIDEO_URL = 'https://api.upload-post.com/api/upload'
UPLOAD_POST_PHOTO_URL = 'https://api.upload-post.com/api/upload_photos'


def _title_from_project(project) -> str:
    """Liefert den Video-Titel-Fallback ohne 'Geschenk'-Praefix.

    project.title ist typisch 'Geschenk Augenoptiker' — fuer Social-Media-
    Titel reicht aber 'Augenoptiker'. Wenn project.topic existiert, wird der
    bevorzugt; sonst project.title mit gestripptem 'Geschenk'-Praefix.
    """
    raw = (project.topic or project.title or '').strip()
    # 'Geschenk ' / 'geschenk ' / 'Geschenk-' Praefix entfernen
    import re
    cleaned = re.sub(r'^(geschenk[\s\-:]+)', '', raw, count=1, flags=re.IGNORECASE)
    return (cleaned or raw)[:100]


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

        # Auto-Title + Description via GLM (Naturmacher-Brand-Voice) —
        # vidgen liefert generische Defaults ("Automatisch generiert mit VidGen
        # Template: ..."), die sind nicht social-tauglich. Wir generieren neu.
        if not title or not description:
            gen_title, gen_desc = self._generate_video_caption()
            title = title or gen_title or _title_from_project(self.project)
            description = description or gen_desc or f'Magvis-Video zum Thema "{self.project.topic}"'

        try:
            video.video_file.open('rb')
            video_bytes = video.video_file.read()
            video.video_file.close()
        except Exception as exc:
            return {'success': False, 'error': f'Video-Datei nicht lesbar: {exc}'}

        # IG Reels lehnt MP4s ab, deren moov-Atom nicht am Anfang steht
        # (kein faststart). YouTube/TikTok ist das egal. Defensiv remuxen.
        video_bytes = _ensure_faststart(video_bytes)

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

    def _generate_video_caption(self) -> tuple[str, str]:
        """GLM erzeugt Title (≤100) + Description (≤500) im Naturmacher-Stil
        + Hashtags am Ende der Description.

        Liefert ('', '') bei GLM-Fehler — Caller fällt dann auf Defaults zurück.
        """
        from .llm_client import MagvisLLMClient
        try:
            glm = MagvisLLMClient(self.user, self.magvis_settings)
        except Exception as exc:
            logger.warning('GLM-Init für Video-Caption: %s', exc)
            return ('', '')
        prompt = (
            f'Erstelle einen Social-Media-Post (TikTok/Instagram/YouTube Shorts) '
            f'für ein 60-Sekunden-Video von Naturmacher.de zum Thema:\n'
            f'"{self.project.topic}"\n\n'
            f'Naturmacher.de verkauft personalisierte Blumentöpfe mit Lasergravur '
            f'als Geschenk. Marken-Voice: herzlich, persönlich, naturverbunden, '
            f'du-Form, deutscher Familienbetrieb.\n\n'
            f'Anforderungen:\n'
            f'- **title**: max 100 Zeichen, hookig, neugierig machend, deutsch.\n'
            f'  ⚠️ WICHTIG: Beginne den Titel NICHT mit "Geschenk" — das wirkt'
            f'  werblich. Stell stattdessen den Beruf/Anlass in den Mittelpunkt.\n'
            f'  ✅ GUT: "Augenoptiker, die das wirklich berührt 💚"\n'
            f'  ✅ GUT: "Was schenkst du eigentlich der Erzieherin?"\n'
            f'  ✅ GUT: "Athletiktrainer-Abschied: 5 Ideen die wirklich bleiben"\n'
            f'  ❌ NICHT: "Geschenk Augenoptiker", "Geschenk-Idee für Erzieherin"\n'
            f'  Kein "Automatisch generiert", kein Template-Hinweis.\n'
            f'- **description**: max 500 Zeichen, beschreibt was das Video zeigt + '
            f'  warum es relevant ist + Call-to-Action, endet mit 5-7 passenden '
            f'  deutschen Hashtags. Erwähne dass es um personalisierte Blumentöpfe '
            f'  von Naturmacher geht, ohne "verkaufen"-Stil. Du-Form. Keine Emojis '
            f'  am Anfang, höchstens 1-2 in der Mitte.\n\n'
            f'Antwort als JSON: {{"title": "...", "description": "..."}}'
        )
        try:
            data = glm.json_chat(prompt, temperature=0.65)
            if isinstance(data, dict):
                return (str(data.get('title', ''))[:100],
                        str(data.get('description', ''))[:500])
        except Exception as exc:
            logger.warning('GLM-Video-Caption fehlgeschlagen: %s', exc)
        return ('', '')

    def poll_until_complete(self, max_wait_s: int = 600, interval_s: int = 15) -> dict:
        """Pollt bis Upload-Post status='completed' oder Timeout.

        - Sobald YouTube-URL verfügbar: project.youtube_url + youtube_video_id sofort gesetzt
          (damit Blog-Stage parallel starten kann).
        - Erfolge pro Plattform → video.social_posted_urls.
        - Fehler pro Plattform → video.social_post_error als JSON
          {platform: error_message}, damit Report/Telegram sehen kann was schiefging.
        - Liefert Summary: posted_urls + failed_platforms.
        """
        api_key = getattr(self.user, 'upload_post_api_key', None) or getattr(self.user, 'uploadpost_api_key', None)
        if not api_key or not self.project.posted_video or not self.project.posted_video.social_request_id:
            return {'success': False, 'error': 'Status-Polling unmöglich (Key/RequestID fehlt)'}

        video = self.project.posted_video
        deadline = time.time() + max_wait_s
        last_data: dict | None = None
        yt_persisted = False

        while time.time() < deadline:
            try:
                resp = requests.get(
                    'https://api.upload-post.com/api/uploadposts/status'
                    f'?request_id={video.social_request_id}',
                    headers={'Authorization': f'Apikey {api_key.strip()}'},
                    timeout=30,
                )
                resp.raise_for_status()
                last_data = resp.json()
            except Exception as exc:
                logger.warning('Polling-Fehler: %s', exc)
                time.sleep(interval_s)
                continue

            posted_urls, failed = self._parse_results(last_data)

            if posted_urls.get('youtube') and not yt_persisted:
                yt_url = posted_urls['youtube']
                video_id = extract_video_id(yt_url)
                self.project.youtube_url = yt_url
                self.project.youtube_video_id = video_id or ''
                self.project.save(update_fields=['youtube_url', 'youtube_video_id', 'updated_at'])
                yt_persisted = True

            status = (last_data or {}).get('status', '')
            completed = (last_data or {}).get('completed', 0)
            total = (last_data or {}).get('total', 0)
            if status == 'completed' or (total and completed >= total):
                self._persist_results(video, posted_urls, failed)
                return {
                    'success': bool(posted_urls),
                    'youtube_url': posted_urls.get('youtube', ''),
                    'video_id': self.project.youtube_video_id,
                    'posted_urls': posted_urls,
                    'failed_platforms': failed,
                }

            time.sleep(interval_s)

        # Timeout — speichere was wir haben
        posted_urls, failed = self._parse_results(last_data or {})
        self._persist_results(video, posted_urls, failed)
        if not failed:
            failed = {'_timeout': f'Polling-Timeout nach {max_wait_s}s'}
        return {
            'success': bool(posted_urls.get('youtube')),
            'error': 'Timeout beim Warten auf alle Plattformen',
            'youtube_url': posted_urls.get('youtube', ''),
            'posted_urls': posted_urls,
            'failed_platforms': failed,
            'last_data': last_data,
        }

    @staticmethod
    def _parse_results(data: dict) -> tuple[dict, dict]:
        posted_urls: dict = {}
        failed: dict = {}
        for item in (data or {}).get('results') or []:
            if not isinstance(item, dict):
                continue
            platform = item.get('platform', '')
            if not platform:
                continue
            if item.get('success'):
                url = item.get('post_url') or item.get('url') or ''
                if url:
                    posted_urls[platform] = url
            else:
                err = item.get('error_message') or item.get('error') or 'Unbekannter Fehler'
                failed[platform] = str(err)[:500]
        if not posted_urls:
            fb = (data or {}).get('posted_urls') or (data or {}).get('urls') or {}
            if isinstance(fb, dict):
                posted_urls = fb
        return posted_urls, failed

    @staticmethod
    def _persist_results(video, posted_urls: dict, failed: dict) -> None:
        import json as _json
        fields = []
        if posted_urls:
            video.social_posted_urls = posted_urls
            fields.append('social_posted_urls')
        if failed:
            video.social_post_error = _json.dumps(failed, ensure_ascii=False)[:1000]
            fields.append('social_post_error')
        if fields:
            video.save(update_fields=fields)

    # Backwards-compat Alias
    def poll_youtube_url(self, max_wait_s: int = 600, interval_s: int = 15) -> dict:
        return self.poll_until_complete(max_wait_s=max_wait_s, interval_s=interval_s)


def _moov_is_at_start(blob: bytes) -> bool:
    """Scannt MP4-Top-Level-Boxen und prüft ob 'moov' vor 'mdat' liegt.

    Gibt True zurück bei Zweifelsfällen (kein MP4, parse-Fehler), damit wir
    fremde Container nicht versehentlich kaputt-remuxen.
    """
    try:
        pos = 0
        moov_pos = mdat_pos = None
        while pos + 8 <= len(blob):
            size = struct.unpack('>I', blob[pos:pos + 4])[0]
            box = blob[pos + 4:pos + 8]
            if size == 1 and pos + 16 <= len(blob):
                size = struct.unpack('>Q', blob[pos + 8:pos + 16])[0]
            if size < 8:
                break
            if box == b'moov' and moov_pos is None:
                moov_pos = pos
            elif box == b'mdat' and mdat_pos is None:
                mdat_pos = pos
            if moov_pos is not None and mdat_pos is not None:
                break
            pos += size
        if moov_pos is None or mdat_pos is None:
            return True
        return moov_pos < mdat_pos
    except Exception:
        return True


def _ensure_faststart(blob: bytes) -> bytes:
    """Remuxt MP4 mit '+faststart' wenn moov hinten steht.

    Nutzt ffmpeg -c copy (kein Re-Encode → ~1s pro Video). Fällt bei Fehler
    auf Original-Bytes zurück, damit Upload nicht blockiert wird.
    """
    if _moov_is_at_start(blob):
        return blob
    if not shutil.which('ffmpeg'):
        logger.warning('ffmpeg fehlt — kein faststart-Remux, IG-Posts können fehlschlagen')
        return blob
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'in.mp4')
            dst = os.path.join(tmp, 'out.mp4')
            with open(src, 'wb') as f:
                f.write(blob)
            res = subprocess.run(
                ['ffmpeg', '-y', '-i', src, '-c', 'copy', '-movflags', '+faststart', dst],
                capture_output=True, timeout=60,
            )
            if res.returncode != 0 or not os.path.exists(dst):
                logger.warning('faststart-Remux fehlgeschlagen: %s', res.stderr[-500:].decode('utf-8', 'ignore'))
                return blob
            with open(dst, 'rb') as f:
                out = f.read()
            logger.info('faststart-Remux: %d → %d Bytes', len(blob), len(out))
            return out
    except Exception as exc:
        logger.warning('faststart-Remux Exception: %s', exc)
        return blob

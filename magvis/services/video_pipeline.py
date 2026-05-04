"""Magvis Video-Pipeline: Orchestriert vidgen ohne RunPod/ComfyUI.

Konfiguration wie OpenClaw vidgen-daily:
- Lokales Render auf Hetzner-Server (kein Modal)
- Template-Rotation: job_intro, facts, things_nobody_tells, myth_busting, day_in_life
- Quote + Fact-Box via GLM generiert
- Title-Position center, Voice nova, Progress-Bar gold
"""
from __future__ import annotations

import logging

from ..models import MagvisProject

logger = logging.getLogger(__name__)

# Template-Rotation wie in OpenClaw vidgen-daily/scripts/create_video.py
VIDEO_TEMPLATES = [
    'job_intro',           # 👔 Berufsvorstellung
    'facts',               # 💡 Fakten-Video
    'things_nobody_tells', # 🤐 Dinge die keiner sagt
    'myth_busting',        # 🔍 Mythen aufdecken
    'day_in_life',         # 📅 Ein Tag als...
    'heartfelt',           # 💖 Emotional/Herzlich (neu, 04.05.2026)
]


class MagvisVideoPipeline:
    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)

    def _generate_quote_and_fact(self, title: str) -> tuple[str, str, str]:
        """Generiert Zitat + Fakt via GLM (analog OpenClaw vidgen-daily)
        mit Retry + Fallback."""
        from .llm_client import MagvisLLMClient
        glm = MagvisLLMClient(self.user, self.magvis_settings)
        prompt = (
            f'Erzeuge zum Thema "{title}" EIN inspirierendes deutsches Zitat '
            f'(max 100 Zeichen, mit Autor — fiktiver Autor wie "Aus der Praxis" '
            f'ist OK falls kein berühmtes Zitat passt) UND EINEN überraschenden '
            f'Fakt (max 80 Zeichen, beginnt mit Zahl oder Prozent).\n\n'
            f'Liefere AUSSCHLIESSLICH dieses JSON-Objekt:\n'
            f'{{"quote_text": "Zitat-Text", "quote_author": "Name", "fact": "X% ..."}}\n'
            f'Korrektes Deutsch mit Umlauten.'
        )
        data = {}
        try:
            data = glm.json_chat_with_retry(prompt, expect='object', max_tokens=400, retries=3) or {}
        except Exception as exc:
            logger.warning('Quote/Fact-Gen Versuch 1 fehlgeschlagen: %s', exc)
        # Fallback bei leerem Result: einfacher GLM-Call ohne JSON-Strenge
        if not data.get('quote_text') or not data.get('fact'):
            try:
                txt = glm.text(
                    f'Schreibe ein deutsches Zitat (max 100 Zeichen) zu "{title}", '
                    f'eine Zeile so:\n'
                    f'ZITAT: <Zitat-Text>\n'
                    f'AUTOR: <Name>\n'
                    f'FAKT: <überraschender Fakt mit Zahl, max 80 Zeichen>',
                    temperature=0.5,
                ) or ''
                for line in txt.split('\n'):
                    if line.startswith('ZITAT:') and not data.get('quote_text'):
                        data['quote_text'] = line.split(':', 1)[1].strip()
                    elif line.startswith('AUTOR:') and not data.get('quote_author'):
                        data['quote_author'] = line.split(':', 1)[1].strip()
                    elif line.startswith('FAKT:') and not data.get('fact'):
                        data['fact'] = line.split(':', 1)[1].strip()
            except Exception as exc:
                logger.warning('Quote/Fact-Fallback fehlgeschlagen: %s', exc)
        return (
            (data.get('quote_text') or '').strip()[:100],
            (data.get('quote_author') or 'Naturmacher').strip()[:50],
            (data.get('fact') or '').strip()[:80],
        )

    def _attach_overlay_image(self, vidgen_project) -> bool:
        """Setzt das Naturmacher-Mockup-Bild als Overlay (analog OpenClaw)."""
        from imageforge.models import ImageGeneration
        from django.core.files.base import ContentFile
        import os
        # ImageGeneration 760 ist das hartkodierte Naturmacher-Mockup-Overlay
        # (so wie in OpenClaw vidgen-daily/scripts/create_video.py:157)
        g = ImageGeneration.objects.filter(id=760).first()
        if not g or not g.generated_image:
            logger.warning('ImageGen 760 (Overlay-Mockup) fehlt — kein Overlay gesetzt')
            return False
        try:
            with open(g.generated_image.path, 'rb') as fh:
                vidgen_project.overlay_file.save(
                    os.path.basename(g.generated_image.path),
                    ContentFile(fh.read()), save=True,
                )
            return True
        except Exception as exc:
            logger.warning('Overlay-Datei konnte nicht gesetzt werden: %s', exc)
            return False

    def _next_template(self) -> str:
        """Rotiert durch die 5 OpenClaw-Templates basierend auf der bisherigen
        Magvis-Project-Anzahl pro User (deterministische Reihenfolge)."""
        try:
            count = MagvisProject.objects.filter(user=self.user).count()
        except Exception:
            count = 0
        return VIDEO_TEMPLATES[count % len(VIDEO_TEMPLATES)]

    def create_video_project(self) -> 'vidgen.models.VideoProject':
        """Erstellt das vidgen-VideoProject im OpenClaw-Stil."""
        from vidgen.models import VideoProject

        title = (self.project.title or self.project.topic)[:200]
        # Quote + Fact via GLM
        quote_text, quote_author, fact_text = self._generate_quote_and_fact(title)
        # Template-Rotation — IGNORIERE alte default_video_template-Settings
        # ('youtube_short' war Magvis-Default, OpenClaw rotiert über 5 Templates).
        template = self._next_template()

        # Topic + Keywords als custom_script-Hint
        custom_script = ''
        if self.project.keywords:
            custom_script = (
                f'Thema: {self.project.topic}\n'
                f'Keywords: {", ".join(self.project.keywords)}'
            )

        vidgen_project = VideoProject.objects.create(
            user=self.user,
            title=title,
            custom_script=custom_script,
            template=template,
            platform='tiktok',
            # OpenClaw-Werte hardcodiert — alte Magvis-Settings ignorieren
            voice='nova',
            title_position='center',
            target_duration=60,
            resolution='1080p',
            render_backend='local',
            watermark=False,
            overlay_start=16,
            overlay_position='top',
            overlay_width=90,
            overlay_duration=5,
            intro_style='none',
            show_progress_bar=True,
            progress_bar_color='#FFD700',
            quote_text=quote_text,
            quote_author=quote_author,
            quote_time=10,
            quote_duration=5,
            fact_box_text=fact_text,
            fact_box_time=25,
            fact_box_duration=5,
        )
        # Overlay-Bild setzen (Naturmacher-Mockup wie in OpenClaw)
        self._attach_overlay_image(vidgen_project)
        self.project.vidgen_project = vidgen_project
        self.project.save(update_fields=['vidgen_project', 'updated_at'])
        return vidgen_project

    def trigger_render(self, sync: bool = True) -> str | dict:
        """Startet die vidgen-Pipeline.

        Mit sync=True (Default): synchron im aktuellen Prozess —
        notwendig wenn wir aus einem Solo-Pool-Worker laufen, der sich
        sonst selbst deadlockt (kein zweiter Worker fuer den vidgen-Task).
        Mit sync=False: per Celery-delay (eigene Queue empfohlen).
        """
        from vidgen.tasks import generate_video

        if not self.project.vidgen_project:
            self.create_video_project()

        vp_id = self.project.vidgen_project.id
        if sync:
            # Bypass Celery — vidgen.generate_video.run() laeuft inline.
            # Das laesst den Stage-Worker bis zum Video-Ende blockieren,
            # ist aber im Solo-Pool die einzig deadlock-freie Option.
            return generate_video.run(vp_id)

        async_result = generate_video.delay(vp_id)
        task_ids = self.project.task_ids or {}
        task_ids['video'] = async_result.id
        self.project.task_ids = task_ids
        self.project.save(update_fields=['task_ids', 'updated_at'])
        return async_result.id

    def is_done(self) -> tuple[bool, str | None]:
        """Prüft ob das vidgen-Projekt fertig ist. Liefert (done, error_or_video_path)."""
        if not self.project.vidgen_project:
            return False, None
        self.project.vidgen_project.refresh_from_db()
        status = self.project.vidgen_project.status
        if status == 'done':
            return True, None
        if status == 'failed':
            return True, self.project.vidgen_project.error_message or 'Video-Render fehlgeschlagen'
        return False, None

    def attach_video_record(self) -> 'videos.Video | None':
        """Holt das von save_to_videos_app erzeugte videos.Video-Objekt."""
        from videos.models import Video
        if not self.project.vidgen_project:
            return None
        # vidgen.tasks.save_to_videos_app erzeugt ein videos.Video für den User
        # Wir suchen das jüngste Video, das nach Projektstart erstellt wurde.
        video = (
            Video.objects.filter(user=self.user, created_at__gte=self.project.vidgen_project.created_at)
            .order_by('-created_at').first()
        )
        if video:
            self.project.posted_video = video
            self.project.save(update_fields=['posted_video', 'updated_at'])
        return video

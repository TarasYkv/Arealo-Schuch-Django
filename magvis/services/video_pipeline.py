"""Magvis Video-Pipeline: Orchestriert vidgen ohne RunPod/ComfyUI.

Nutzt den vorhandenen vidgen.tasks.generate_video() Celery-Task,
der die volle Pipeline (Skript → Audio → Pexels-Clips → Modal-Render → Compress → Save)
durchführt. RunPod kommt dabei nicht zum Einsatz, da fetch_pexels_clips_smart
ausschließlich Pexels-Stock-Footage nutzt.
"""
from __future__ import annotations

import logging

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisVideoPipeline:
    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)

    def create_video_project(self) -> 'vidgen.models.VideoProject':
        """Erstellt das vidgen-VideoProject."""
        from vidgen.models import VideoProject

        title = (self.project.title or self.project.topic)[:200]

        # Topic + Keywords als custom_script-Hint hinzufügen
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
            template=self.magvis_settings.default_video_template or 'youtube_short',
            platform='youtube_shorts',
            voice=self.magvis_settings.default_voice or 'alloy',
            target_duration=self.magvis_settings.default_video_duration or 45,
            resolution='1080p',
            render_backend='modal',
        )
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

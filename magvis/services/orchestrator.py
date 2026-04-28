"""Magvis Orchestrator — Stage-Dispatch.

Ruft den passenden Sub-Service je nach Stage des Projekts auf.
Wird von den Celery-Tasks und der DRF-API genutzt.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisOrchestrator:
    """Orchestriert die Stages eines MagvisProject."""

    STAGE_SLUGS = ['video', 'post_video', 'products', 'blog', 'image_posts', 'report']

    def __init__(self, project: MagvisProject):
        self.project = project

    # ------------------------------------------------------------------ public

    def run_stage(self, slug: str, **kwargs) -> dict:
        """Synchron einen Stage ausführen."""
        if slug not in self.STAGE_SLUGS:
            raise ValueError(f'Unbekannter Stage-Slug: {slug}')

        method = getattr(self, f'_stage_{slug}')
        try:
            self._set_stage_running(slug)
            result = method(**kwargs)
            self._set_stage_done(slug, result)
            return result
        except Exception as exc:
            logger.exception('Stage %s fehlgeschlagen', slug)
            self.project.stage = MagvisProject.STAGE_FAILED
            self.project.error_message = str(exc)[:2000]
            self.project.save(update_fields=['stage', 'error_message', 'updated_at'])
            raise

    def advance(self) -> dict | None:
        """Führt den nächsten passenden Stage aus, basierend auf project.stage."""
        slug = self.project.next_stage_slug()
        if not slug:
            return None
        return self.run_stage(slug)

    def run_full_chain(self) -> None:
        """Komplette Pipeline ohne Pause (für scheduled Auto-Runs)."""
        for slug in self.STAGE_SLUGS:
            try:
                self.run_stage(slug)
            except Exception:
                # Stage-Fehler unterbricht die Chain (Project ist auf 'failed' gesetzt)
                # Report-Stage läuft trotzdem mit Fehler-Notiz
                if slug != 'report':
                    try:
                        self.run_stage('report')
                    except Exception:
                        pass
                raise

    # ----------------------------------------------------------------- stages

    def _stage_video(self, **kwargs) -> dict:
        """Video-Stage: vidgen synchron im selben Worker.

        Der pool=solo Celery-Worker kann den vidgen-Task nicht parallel
        abarbeiten, deshalb kein .delay() + Polling-Deadlock — sondern
        direkter Aufruf von vidgen.tasks.generate_video.run().
        """
        from .video_pipeline import MagvisVideoPipeline
        pipe = MagvisVideoPipeline(self.project)
        pipe.create_video_project()
        result = pipe.trigger_render(sync=True)
        # vidgen markiert sein VideoProject am Ende auf status='done' oder 'failed'
        done, err = pipe.is_done()
        if not done:
            raise RuntimeError('Video-Pipeline lief, aber VideoProject ist nicht done/failed')
        if err:
            raise RuntimeError(f'Video-Generierung fehlgeschlagen: {err}')
        pipe.attach_video_record()
        return {'success': True, 'video_result': result}

    def _stage_post_video(self, **kwargs) -> dict:
        from .social_pipeline import MagvisSocialPipeline
        pipe = MagvisSocialPipeline(self.project)
        result = pipe.post_video()
        if not result.get('success'):
            raise RuntimeError(f'Video-Posten fehlgeschlagen: {result.get("error")}')
        # Auf YouTube-URL warten
        poll = pipe.poll_youtube_url(max_wait_s=600)
        if not poll.get('success'):
            # Trotzdem als done markieren — Blog kann ohne YT-Embed gebaut werden
            logger.warning('YouTube-URL nicht verfügbar: %s', poll.get('error'))
        return {'success': True, **poll}

    def _stage_products(self, **kwargs) -> dict:
        from .product_pipeline import MagvisProductPipeline
        return MagvisProductPipeline(self.project).run()

    def _stage_blog(self, **kwargs) -> dict:
        from .blog_assembler import MagvisBlogAssembler
        blog = MagvisBlogAssembler(self.project).assemble()
        return {'success': True, 'blog_id': blog.id, 'shopify_url': blog.shopify_published_url}

    def _stage_image_posts(self, **kwargs) -> dict:
        """Schritt 5 ist meistens manuell (UI). Hier: Auto-Post wenn target_platforms gesetzt."""
        from .image_post_pipeline import MagvisImagePostPipeline
        results = []
        assets = self.project.image_assets.all()
        for asset in assets:
            if not asset.target_platforms:
                continue  # User hat noch nichts gewählt — überspringen
            try:
                r = MagvisImagePostPipeline(asset).post(
                    platforms=asset.target_platforms,
                    use_overlay=asset.use_overlay,
                    overlay_text=asset.overlay_text,
                    overlay_method=asset.overlay_method,
                    title=asset.title_de,
                    description=asset.description_de,
                )
                results.append({'asset_id': asset.id, 'result': r})
            except Exception as exc:
                logger.exception('ImagePost asset=%s', asset.id)
                results.append({'asset_id': asset.id, 'error': str(exc)})
        return {'success': True, 'count': len(results), 'results': results}

    def _stage_report(self, **kwargs) -> dict:
        from .report_mailer import send_project_report
        ok = send_project_report(self.project)
        return {'success': ok}

    # --------------------------------------------------------------- internals

    STAGE_RUNNING_MAP = {
        'video': MagvisProject.STAGE_VIDEO_RUNNING,
        'post_video': MagvisProject.STAGE_POST_VIDEO_RUNNING,
        'products': MagvisProject.STAGE_PRODUCTS_RUNNING,
        'blog': MagvisProject.STAGE_BLOG_RUNNING,
        'image_posts': MagvisProject.STAGE_IMAGE_POSTS_RUNNING,
        'report': MagvisProject.STAGE_REPORT_SENT,
    }
    STAGE_DONE_MAP = {
        'video': MagvisProject.STAGE_VIDEO_DONE,
        'post_video': MagvisProject.STAGE_POST_VIDEO_DONE,
        'products': MagvisProject.STAGE_PRODUCTS_DONE,
        'blog': MagvisProject.STAGE_BLOG_DONE,
        'image_posts': MagvisProject.STAGE_IMAGE_POSTS_DONE,
        'report': MagvisProject.STAGE_COMPLETED,
    }
    STAGE_PCT = {
        'video': 30, 'post_video': 45, 'products': 65,
        'blog': 85, 'image_posts': 95, 'report': 100,
    }

    def _set_stage_running(self, slug: str) -> None:
        self.project.stage = self.STAGE_RUNNING_MAP[slug]
        self.project.error_message = ''
        self.project.log_stage(slug, f'Stage "{slug}" gestartet', level='info')
        self.project.save(update_fields=['stage', 'error_message', 'updated_at'])

    def _set_stage_done(self, slug: str, result: dict | None = None) -> None:
        self.project.stage = self.STAGE_DONE_MAP[slug]
        self.project.progress_pct = self.STAGE_PCT[slug]
        msg = f'Stage "{slug}" erfolgreich abgeschlossen'
        if result and result.get('shopify_url'):
            msg += f' — {result["shopify_url"]}'
        self.project.log_stage(slug, msg, level='success')
        self.project.save(update_fields=['stage', 'progress_pct', 'updated_at'])

        # Bei letztem Stage: Wenn source_queue_item existiert → Status setzen
        if slug == 'report' and self.project.source_queue_item:
            self.project.source_queue_item.refresh_from_db()
            self.project.source_queue_item.used_by_project = self.project
            self.project.source_queue_item.save(update_fields=['used_by_project'])

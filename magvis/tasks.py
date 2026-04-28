"""Celery-Tasks für Magvis."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def run_full_chain(self, project_id):
    """Führt den kompletten Magvis-Workflow für ein Projekt aus."""
    from .models import MagvisProject
    from .services.orchestrator import MagvisOrchestrator

    project = MagvisProject.objects.get(id=project_id)
    project.celery_eta_task_id = self.request.id
    project.save(update_fields=['celery_eta_task_id'])
    MagvisOrchestrator(project).run_full_chain()
    return {'project_id': str(project_id), 'final_stage': project.stage}


@shared_task(bind=True, soft_time_limit=3600, time_limit=3660)
def run_stage_async(self, project_id, slug, kwargs=None):
    """Führt einen einzelnen Stage async aus."""
    from .models import MagvisProject
    from .services.orchestrator import MagvisOrchestrator

    project = MagvisProject.objects.get(id=project_id)
    task_ids = project.task_ids or {}
    task_ids[slug] = self.request.id
    project.task_ids = task_ids
    project.save(update_fields=['task_ids'])

    return MagvisOrchestrator(project).run_stage(slug, **(kwargs or {}))


@shared_task(bind=True, soft_time_limit=600, time_limit=660)
def post_image_async(self, asset_id, platforms, use_overlay=False,
                     overlay_text='', overlay_method='pil', title='', description=''):
    from .models import MagvisImageAsset
    from .services.image_post_pipeline import MagvisImagePostPipeline

    asset = MagvisImageAsset.objects.get(id=asset_id)
    return MagvisImagePostPipeline(asset).post(
        platforms=platforms, use_overlay=use_overlay,
        overlay_text=overlay_text, overlay_method=overlay_method,
        title=title or None, description=description or None,
    )


@shared_task
def auto_run_from_queue():
    """Cron-Job: Pop nächstes pending-Topic je User mit auto_run_enabled und starte Workflow."""
    from .models import MagvisProject, MagvisSettings, MagvisTopicQueue

    started = 0
    for s in MagvisSettings.objects.filter(auto_run_enabled=True):
        item = MagvisTopicQueue.pop_next(s.user)
        if not item:
            continue
        project = MagvisProject.objects.create(
            user=s.user,
            title=item.topic[:255],
            topic=item.topic,
            keywords=item.keywords,
            target_audience=item.target_audience,
            auto_advance=True,
            source_queue_item=item,
        )
        async_result = run_full_chain.delay(str(project.id))
        project.celery_eta_task_id = async_result.id
        project.save(update_fields=['celery_eta_task_id'])
        started += 1
    return {'started': started}


def schedule_project(project) -> str | None:
    """Plant ein Projekt zur scheduled_at-Zeit ein. Liefert celery-task-id oder None."""
    from celery.result import AsyncResult

    if not project.scheduled_at or project.scheduled_at <= timezone.now():
        return None

    # Alten ETA-Task abbrechen
    if project.celery_eta_task_id:
        try:
            AsyncResult(project.celery_eta_task_id).revoke()
        except Exception:
            pass

    async_result = run_full_chain.apply_async(args=[str(project.id)], eta=project.scheduled_at)
    project.celery_eta_task_id = async_result.id
    from .models import MagvisProject
    project.stage = MagvisProject.STAGE_SCHEDULED
    project.save(update_fields=['celery_eta_task_id', 'stage', 'updated_at'])
    return async_result.id

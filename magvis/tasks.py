"""Celery-Tasks für Magvis."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def run_full_chain(self, project_id):
    """Führt den kompletten Magvis-Workflow für ein Projekt aus.

    Project-Lock: pro Project laeuft maximal 1 run_full_chain gleichzeitig.
    Wenn ein anderer Task fuer dasselbe Project bereits aktiv ist, wird der
    neue Trigger ohne Wirkung verworfen — verhindert Doppel-Posting bei
    akkumulierten Re-Triggers.
    """
    from django.db import transaction
    from .models import MagvisProject
    from .services.orchestrator import MagvisOrchestrator

    # Atomar: pruefe ob ein anderer aktiver Task fuer dieses Project laeuft
    with transaction.atomic():
        project = MagvisProject.objects.select_for_update().get(id=project_id)
        active_task = project.celery_eta_task_id or ''
        if active_task and active_task != self.request.id:
            # Pruefen ob der angebliche aktive Task wirklich noch laeuft
            from celery.result import AsyncResult
            existing = AsyncResult(active_task)
            if existing.state in ('PENDING', 'STARTED', 'RECEIVED'):
                logger.warning(
                    'run_full_chain SKIPPED — Project %s hat bereits aktiven Task %s',
                    project_id, active_task,
                )
                return {'project_id': str(project_id), 'skipped': True,
                        'reason': f'duplicate_task (active={active_task})'}
            # Sonst: Stale Lock, freigeben
        project.celery_eta_task_id = self.request.id
        project.save(update_fields=['celery_eta_task_id'])

    try:
        MagvisOrchestrator(project).run_full_chain()
    finally:
        # Lock loesen — auch bei Fehler
        project.refresh_from_db()
        if project.celery_eta_task_id == self.request.id:
            project.celery_eta_task_id = ''
            project.save(update_fields=['celery_eta_task_id'])
    return {'project_id': str(project_id), 'final_stage': project.stage}


@shared_task
def cleanup_stuck_magvis_stages():
    """Beat-Task: Setzt Magvis-Projects mit Stage *_running und alter
    updated_at (>30 Min) auf 'failed'. Raeumt Geister-Stages auf — falls ein
    Worker abgestuerzt ist und die DB im Running-State haengt.
    """
    from datetime import timedelta
    from .models import MagvisProject
    threshold = timezone.now() - timedelta(minutes=30)
    stuck = MagvisProject.objects.filter(
        stage__contains='_running', updated_at__lt=threshold,
    )
    count = 0
    for p in stuck:
        old_stage = p.stage
        p.stage = MagvisProject.STAGE_FAILED
        p.error_message = (
            f'Auto-Cleanup: Stage "{old_stage}" hing über 30 Min ohne Update — '
            f'Worker vermutlich abgestuerzt. (Aufgeräumt {timezone.now():%H:%M})'
        )
        p.celery_eta_task_id = ''  # Lock freigeben
        p.save(update_fields=['stage', 'error_message', 'celery_eta_task_id'])
        count += 1
        logger.warning('Stuck-Cleanup: Project %s (%s) auf failed gesetzt', p.id, old_stage)
    return {'cleaned': count}


@shared_task
def resume_unfinished_magvis_projects():
    """Beat-Task: Findet Projekte in *_done-Stages (NICHT 'completed'/'failed')
    und re-triggert run_full_chain.

    Ursachen warum Projekte hier landen:
    - Worker-Crash zwischen Stages (Done-Save erfolgreich, aber for-Loop unterbrochen)
    - Code-Deploy mit Worker-Restart mitten in der Pipeline
    - Celery-Task-Lost ohne Retry (z.B. soft_time_limit erreicht)

    Sicherheits-Garantien:
    - Project-Lock in run_full_chain verhindert Doppel-Trigger
    - Stage-Idempotenz (products: shopify_product_id-Check, blog: article_id-Check,
      image_posts: posted_status-Check, collection: shopify_collection_id-Check)
      verhindern Doppel-Erstellung
    - Mindest-Alter 10 min — verhindert Eingriff in noch laufende Tasks
    """
    from datetime import timedelta
    from .models import MagvisProject

    DONE_STAGES_TO_RESUME = [
        MagvisProject.STAGE_VIDEO_DONE,
        MagvisProject.STAGE_POST_VIDEO_DONE,
        MagvisProject.STAGE_PRODUCTS_DONE,
        MagvisProject.STAGE_BLOG_DONE,
        MagvisProject.STAGE_IMAGE_POSTS_DONE,
    ]
    threshold = timezone.now() - timedelta(minutes=10)
    candidates = MagvisProject.objects.filter(
        stage__in=DONE_STAGES_TO_RESUME, updated_at__lt=threshold,
    )
    resumed = []
    for p in candidates:
        # Lock prüfen — wenn schon ein aktiver Task läuft, nicht erneut triggern
        if p.celery_eta_task_id:
            from celery.result import AsyncResult
            existing = AsyncResult(p.celery_eta_task_id)
            if existing.state in ('PENDING', 'STARTED', 'RECEIVED'):
                continue  # Lebt noch, nichts tun
        try:
            res = run_full_chain.delay(str(p.id))
            resumed.append({'id': str(p.id), 'stage': p.stage, 'task': res.id})
            logger.info('Auto-Resume: Project %s (%s) → Task %s', p.id, p.stage, res.id)
        except Exception as exc:
            logger.warning('Auto-Resume Project %s fehlgeschlagen: %s', p.id, exc)
    return {'resumed': len(resumed), 'projects': resumed}


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

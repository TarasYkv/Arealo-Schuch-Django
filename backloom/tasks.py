"""Backloom Celery-Tasks fuer die Submission-Pipeline.

Queue: ``backlink`` (separat vom Magvis-Worker, damit lange Magvis-Pipelines
einen Submission-Run nicht blockieren).

Wichtig: Die Tasks rufen den BotRunner synchron auf (er ist intern blockierend
und schliesst sein eigenes Browser-Session-Lifecycle). Eine Task = eine
Submission. Pro Container kann nur 1 Session zur Zeit laufen — Concurrency
auf der Queue daher = 1.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import (
    BacklinkSource,
    NaturmacherProfile,
    SubmissionAttempt,
    SubmissionAttemptStatus,
)
from .services.bot_runner import BotRunner

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='backlink', name='backloom.submit_backlink',
             autoretry_for=(), max_retries=0)
def submit_backlink_task(self, source_id: str, profile_id: int,
                         attempt_id: str | None = None) -> dict:
    """Fuehrt eine Submission fuer eine BacklinkSource aus.

    Args:
        source_id: UUID der BacklinkSource.
        profile_id: PK des NaturmacherProfile.
        attempt_id: optional — wenn gesetzt, wird ein bestehender Attempt
            wiederverwendet (z.B. nach Manual-Intervention). Sonst neu erstellen.

    Returns:
        Dict mit status + attempt_id + key-Felder fuer den Aufrufer.
    """
    source = BacklinkSource.objects.get(pk=source_id)
    profile = NaturmacherProfile.objects.get(pk=profile_id)

    if attempt_id:
        attempt = SubmissionAttempt.objects.get(pk=attempt_id)
        logger.info('Existierenden Attempt %s fortsetzen (Status %s)',
                    attempt.id, attempt.status)
    else:
        attempt = SubmissionAttempt.objects.create(
            source=source,
            profile=profile,
            status=SubmissionAttemptStatus.QUEUED,
        )
        logger.info('Neuer Attempt %s fuer %s', attempt.id, source.domain)

    runner = BotRunner(attempt)
    result = runner.run()

    return {
        'attempt_id': str(result.id),
        'status': result.status,
        'backlink_url': result.backlink_url,
        'duration_s': result.duration_seconds,
    }


@shared_task(queue='backlink', name='backloom.verify_backlink')
def verify_backlink_task(attempt_id: str) -> dict:
    """Prueft 24h nach Submission ob der Backlink wirklich live ist.

    Wird in Phase 6 ausgebaut. MVP-Stub damit der Task-Name registriert ist.
    """
    attempt = SubmissionAttempt.objects.get(pk=attempt_id)
    if not attempt.backlink_url:
        return {'attempt_id': str(attempt.id), 'verified': False, 'reason': 'no url'}
    # TODO Phase 6: HTTP-Fetch + naturmacher.de-Suche + DoFollow-Check
    attempt.last_verified_at = timezone.now()
    attempt.save(update_fields=['last_verified_at', 'updated_at'])
    return {'attempt_id': str(attempt.id), 'verified': None,
            'reason': 'verifier-stub Phase 6'}

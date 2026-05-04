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
    """Verifiziert einen einzelnen SubmissionAttempt (Phase 6.1).

    Sucht nach naturmacher.de-Backlink auf candidate_url + source.url.
    Updatet Status entsprechend.
    """
    from .services.link_verifier import verify_backlink

    attempt = SubmissionAttempt.objects.select_related('source').get(pk=attempt_id)
    start = []
    if attempt.backlink_url:
        start.append(attempt.backlink_url)
    if attempt.source.url and attempt.source.url not in start:
        start.append(attempt.source.url)
    if not start:
        return {'attempt_id': str(attempt.id), 'verified': False, 'reason': 'no url'}

    result = verify_backlink(start, same_domain_only=True)
    attempt.last_verified_at = timezone.now()
    if result.found:
        attempt.status = SubmissionAttemptStatus.SUCCESS
        attempt.is_verified_live = True
        attempt.is_dofollow = result.is_dofollow
        attempt.backlink_url = result.public_url
        attempt.save(update_fields=[
            'status', 'is_verified_live', 'is_dofollow', 'backlink_url',
            'last_verified_at', 'updated_at',
        ])
        attempt.add_step(
            f'Re-Verify: Backlink LIVE auf {result.public_url[:100]} '
            f'({"DoFollow" if result.is_dofollow else "NoFollow"})',
            level='info',
        )
        return {'attempt_id': str(attempt.id), 'verified': True,
                'public_url': result.public_url, 'dofollow': result.is_dofollow}
    else:
        # Status nur upgraden, nicht downgraden:
        # FAILED_NO_LINK oder PENDING_VERIFY bleibt
        if attempt.status == SubmissionAttemptStatus.PENDING_VERIFY:
            attempt.status = SubmissionAttemptStatus.FAILED_NO_LINK
            attempt.error_message = (
                f'Re-Verify: Kein Link auf {", ".join(result.pages_checked[:3])}'
            )
            attempt.save(update_fields=[
                'status', 'error_message', 'last_verified_at', 'updated_at',
            ])
        else:
            attempt.save(update_fields=['last_verified_at', 'updated_at'])
        return {'attempt_id': str(attempt.id), 'verified': False,
                'pages_checked': result.pages_checked}


@shared_task(queue='backlink', name='backloom.reverify_pending_attempts')
def reverify_pending_attempts() -> dict:
    """Periodischer Re-Verify aller PENDING_VERIFY + FAILED_NO_LINK
    Attempts juenger als 7 Tage. Wird stuendlich von celery-beat getriggert.
    """
    from datetime import timedelta as _td
    cutoff = timezone.now() - _td(days=7)
    qs = SubmissionAttempt.objects.filter(
        status__in=[
            SubmissionAttemptStatus.PENDING_VERIFY,
            SubmissionAttemptStatus.FAILED_NO_LINK,
        ],
        created_at__gte=cutoff,
    )[:50]  # max 50 pro Run um Queue nicht zu fluten

    triggered = 0
    for a in qs:
        # Falls vor < 5 Min schon verifiziert wurde, skip
        if a.last_verified_at and (timezone.now() - a.last_verified_at).total_seconds() < 300:
            continue
        verify_backlink_task.delay(str(a.id))
        triggered += 1
    logger.info('reverify_pending_attempts: %d Tasks ausgeloest', triggered)
    return {'triggered': triggered, 'cutoff_days': 7}

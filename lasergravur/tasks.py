"""Celery-Tasks für Lasergravur."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def poll_lasergravur_orders():
    """Beat-Task alle 2 Min: holt neue Shopify-Orders für alle User mit
    konfigurierter LaserSettings und legt LaserOrder-Records an.
    """
    from .models import LaserSettings
    from .services.shopify_poller import poll_for_user

    results = []
    for s in LaserSettings.objects.all():
        try:
            r = poll_for_user(s.user)
            results.append({'user': s.user.username, **r})
        except Exception as exc:
            logger.exception('poll_for_user(%s)', s.user)
            results.append({'user': s.user.username, 'error': str(exc)})
    return {'polled': len(results), 'results': results}

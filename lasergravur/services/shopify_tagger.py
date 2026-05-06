"""Schreibt Status-Tags zurück nach Shopify wenn LaserOrder Status ändert.

Tags:
- 'lasergravur_designed' → wenn Mitarbeiter im Editor "Bestätigen" klickt
- 'lasergravur_engraved' → wenn Mitarbeiter „Graviert"-Button klickt

So sieht jeder im Shopify-Admin sofort an Order-Tags ob die Gravur erledigt ist.
"""
from __future__ import annotations

import logging

import requests

from ..models import LaserSettings

logger = logging.getLogger(__name__)


def add_tag_to_order(user, shopify_order_id: str, tag: str) -> bool:
    """Fügt einen Tag zur Shopify-Order hinzu (bestehende Tags bleiben).

    Liefert True wenn erfolgreich.
    """
    settings = LaserSettings.objects.filter(user=user).first()
    if not settings or not settings.shopify_store:
        return False
    store = settings.shopify_store
    h = {'X-Shopify-Access-Token': store.access_token,
         'Content-Type': 'application/json'}
    base = f'https://{store.shop_domain}/admin/api/2023-10'

    # Aktuelle Tags holen
    try:
        r = requests.get(f'{base}/orders/{shopify_order_id}.json?fields=tags',
                         headers=h, timeout=15)
        if r.status_code != 200:
            logger.warning('Order %s lesen: HTTP %s', shopify_order_id, r.status_code)
            return False
        existing_tags = r.json().get('order', {}).get('tags', '') or ''
        existing_set = {t.strip() for t in existing_tags.split(',') if t.strip()}
    except Exception as exc:
        logger.warning('Order %s GET: %s', shopify_order_id, exc)
        return False

    if tag in existing_set:
        return True  # Schon drin, nichts zu tun

    existing_set.add(tag)
    new_tags = ', '.join(sorted(existing_set))

    try:
        r = requests.put(
            f'{base}/orders/{shopify_order_id}.json',
            headers=h,
            json={'order': {'id': int(shopify_order_id), 'tags': new_tags}},
            timeout=15,
        )
        if r.status_code in (200, 201):
            logger.info('Order %s Tag hinzugefügt: %s', shopify_order_id, tag)
            return True
        logger.warning('Order %s Tag-Update: HTTP %s', shopify_order_id, r.status_code)
    except Exception as exc:
        logger.warning('Order %s PUT: %s', shopify_order_id, exc)
    return False

"""Polling-Service: holt neue Shopify-Orders alle paar Minuten und legt
LaserOrder-Records an, wenn das Produkt zur Lasergravur gehört.

Wird von magvis.tasks.poll_lasergravur_orders Beat-Task aufgerufen.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.utils import timezone

from ..models import LaserOrder, LaserDesign, LaserSettings

logger = logging.getLogger(__name__)


def poll_for_user(user) -> dict:
    """Holt neue Shopify-Orders für einen User. Liefert Statistik."""
    settings = LaserSettings.objects.filter(user=user).first()
    if not settings or not settings.shopify_store:
        return {'skipped': True, 'reason': 'no settings/store'}
    if not settings.relevant_product_handles:
        return {'skipped': True, 'reason': 'no product handles configured'}

    store = settings.shopify_store
    h = {'X-Shopify-Access-Token': store.access_token}
    base = f'https://{store.shop_domain}/admin/api/2023-10'

    # product_id-Mapping aufbauen wenn leer (für Filter — Shopify liefert
    # product_handle in line_items LEER, wir brauchen product_id-Filter)
    pid_to_model = settings.product_id_to_model or {}
    if not pid_to_model:
        pid_to_model = _build_product_id_map(store, settings)
        settings.product_id_to_model = pid_to_model
        settings.save(update_fields=['product_id_to_model'])

    # Default: letzte 24h, ab dann incrementally seit last_polled_at
    since = (settings.last_polled_at
             or timezone.now() - timedelta(hours=24))
    # 1 Min Puffer wegen Clock-Drift
    since_iso = (since - timedelta(minutes=1)).isoformat()

    params = {
        'status': 'any',
        'fulfillment_status': 'unshipped',  # nur noch nicht versendete (= zu gravieren)
        'created_at_min': since_iso,
        'limit': 100,
        'fields': ('id,name,created_at,line_items,customer,fulfillment_status,'
                   'cancelled_at,shipping_address,note_attributes,email'),
    }
    try:
        r = requests.get(f'{base}/orders.json', headers=h, params=params, timeout=30)
        r.raise_for_status()
    except Exception as exc:
        logger.warning('Shopify-Polling fehlgeschlagen für %s: %s', user, exc)
        return {'error': str(exc)}

    orders = r.json().get('orders', [])

    n_new = 0
    n_skipped = 0
    n_unknown = 0
    for order in orders:
        # Bereits versendete oder stornierte Bestellungen ignorieren
        if order.get('fulfillment_status') == 'fulfilled':
            continue
        if order.get('cancelled_at'):
            continue
        for line in order.get('line_items', []):
            pid = str(line.get('product_id', ''))
            model = pid_to_model.get(pid)
            if not model:
                # Heuristik: hat das line_item Personalisierungs-Properties
                # (Textzeile, Schriftart, Gravur, etc.) UND der Title sagt
                # 'Topf' / 'Pflanz' / 'Gravur' → wahrscheinlich ein Topf
                # den wir noch nicht kennen — als 'unknown' importieren
                # damit der Mitarbeiter ihn manuell bearbeiten kann.
                if _looks_like_unknown_topf(line):
                    model = 'unknown'
                    n_unknown += 1
                else:
                    n_skipped += 1
                    continue
            # LaserOrder anlegen (wenn noch nicht vorhanden)
            created = _create_or_update_laser_order(
                user=user, order=order, line=line,
                topf_model=model,
            )
            if created:
                n_new += 1

    # Bestehende offene Bestellungen mit Shopify-Fulfillment abgleichen —
    # wenn sie inzwischen versendet/storniert wurden, hier auf engraved
    # bzw. failed setzen (sonst stehen ewig "alte" Bestellungen in der Liste).
    n_synced = _sync_fulfillment_status(user, store)

    settings.last_polled_at = timezone.now()
    settings.save(update_fields=['last_polled_at'])
    return {'success': True, 'new_orders': n_new, 'skipped_lines': n_skipped,
            'total_orders_seen': len(orders), 'synced_to_engraved': n_synced}


def _sync_fulfillment_status(user, store) -> int:
    """Prüft offene LaserOrders gegen Shopify und schließt versendete/stornierte ab.

    Liefert Anzahl der auf engraved/failed gesetzten Orders.
    """
    h = {'X-Shopify-Access-Token': store.access_token}
    base = f'https://{store.shop_domain}/admin/api/2023-10'
    open_orders = LaserOrder.objects.filter(user=user).exclude(
        status__in=[LaserOrder.STATUS_ENGRAVED, LaserOrder.STATUS_FAILED])
    # Eindeutige Shopify-Order-IDs (mehrere LaserOrders pro Order möglich)
    shopify_ids = set(open_orders.values_list('shopify_order_id', flat=True))
    if not shopify_ids:
        return 0
    n_synced = 0
    # Batch via ids-Filter (max 250 IDs pro Call)
    ids_list = list(shopify_ids)
    for i in range(0, len(ids_list), 250):
        batch = ids_list[i:i + 250]
        try:
            r = requests.get(f'{base}/orders.json', headers=h, params={
                'ids': ','.join(batch), 'status': 'any', 'limit': 250,
                'fields': 'id,fulfillment_status,cancelled_at',
            }, timeout=30)
            r.raise_for_status()
        except Exception as exc:
            logger.warning('Shopify-Status-Sync Batch fehlgeschlagen: %s', exc)
            continue
        for so in r.json().get('orders', []):
            sid = str(so['id'])
            cancelled = so.get('cancelled_at')
            fulfillment = so.get('fulfillment_status')
            if cancelled:
                # Storniert → failed
                updated = open_orders.filter(shopify_order_id=sid).update(
                    status=LaserOrder.STATUS_FAILED,
                    error_message='Shopify: Bestellung storniert',
                )
                n_synced += updated
            elif fulfillment == 'fulfilled':
                # Versendet/erfüllt → wir nehmen an dass graviert
                updated = open_orders.filter(shopify_order_id=sid).update(
                    status=LaserOrder.STATUS_ENGRAVED,
                    engraved_at=timezone.now(),
                )
                n_synced += updated
    if n_synced:
        logger.info('Fulfillment-Sync: %d Orders auf engraved/failed gesetzt', n_synced)
    return n_synced


def _looks_like_unknown_topf(line: dict) -> bool:
    """Heuristik: hat dieses line_item Personalisierungs-Properties UND
    Title-Hinweise die auf einen Topf deuten? Dann importieren wir es
    als 'unknown' damit der Mitarbeiter es manuell bearbeitet."""
    title = (line.get('title') or '').lower()
    has_topf_word = any(w in title for w in ['topf', 'pflanz', 'gravur', 'graviert'])
    if not has_topf_word:
        return False
    # Hat Personalisierungs-Properties?
    props = line.get('properties') or []
    for p in props:
        name = (p.get('name', '') or '').lower()
        if any(k in name for k in ['textzeile', 'gravur', 'schrift', 'icon', 'symbol', 'name', 'datum', 'zahl']):
            return True
    return False


def _build_product_id_map(store, settings) -> dict:
    """Resolviert product_handle → product_id via Shopify-API.

    Liefert {shopify_product_id_str: model_slug}.
    """
    h = {'X-Shopify-Access-Token': store.access_token}
    base = f'https://{store.shop_domain}/admin/api/2023-10'
    out = {}
    handle_to_model = settings.handle_to_model or {}
    for handle, model in handle_to_model.items():
        try:
            r = requests.get(f'{base}/products.json?handle={handle}&fields=id,handle',
                             headers=h, timeout=15)
            for p in r.json().get('products', []):
                out[str(p['id'])] = model
        except Exception as exc:
            logger.warning('Resolve handle %s: %s', handle, exc)
    logger.info('product_id_to_model gebaut: %d Einträge', len(out))
    return out


def _matches_handles(handle: str, handles: set) -> bool:
    """Erlaubt Prefix-Match — z.B. 'mein-blumentopf-designer' matched alle Varianten."""
    if not handle:
        return False
    return any(h in handle or handle in h for h in handles)


def _handle_from_title(title: str) -> str:
    """Fallback wenn product_handle nicht im line_item ist."""
    from django.utils.text import slugify
    return slugify(title or '')


def _create_or_update_laser_order(user, order: dict, line: dict, topf_model: str):
    """Erstellt LaserOrder + LaserDesign aus Shopify-Order. Liefert True wenn NEU."""
    from .property_parser import parse_design_from_properties

    shopify_order_id = str(order['id'])
    shopify_line_item_id = str(line['id'])

    # Idempotenz: existiert schon?
    existing = LaserOrder.objects.filter(
        user=user,
        shopify_order_id=shopify_order_id,
        shopify_line_item_id=shopify_line_item_id,
    ).first()
    if existing:
        return False

    # Customer-Name
    customer = order.get('customer') or {}
    addr = order.get('shipping_address') or {}
    name = ' '.join(filter(None, [
        customer.get('first_name') or addr.get('first_name'),
        customer.get('last_name') or addr.get('last_name'),
    ])).strip() or '—'

    # Properties aus line_item
    properties = {p.get('name'): p.get('value')
                  for p in (line.get('properties') or [])
                  if p.get('name')}

    laser_order = LaserOrder.objects.create(
        user=user,
        shopify_order_id=shopify_order_id,
        shopify_order_number=order.get('name', ''),
        shopify_customer_name=name,
        shopify_customer_email=customer.get('email', '') or order.get('email', '') or '',
        shopify_product_handle=line.get('product_handle') or '',
        shopify_product_title=line.get('title', ''),
        shopify_line_item_id=shopify_line_item_id,
        shopify_line_item_quantity=int(line.get('quantity', 1)),
        raw_properties=properties,
        topf_model=topf_model,
        status=LaserOrder.STATUS_PENDING,
        shopify_order_created_at=_parse_iso(order.get('created_at')),
    )

    # Auto-Design aus Properties versuchen
    try:
        design_data, complete = parse_design_from_properties(properties, topf_model)
        LaserDesign.objects.create(order=laser_order, **design_data)
        laser_order.status = (LaserOrder.STATUS_AUTO_DESIGNED if complete
                              else LaserOrder.STATUS_NEEDS_MANUAL)
        laser_order.save(update_fields=['status'])
    except Exception as exc:
        logger.exception('Property-Parser für Order %s', shopify_order_id)
        laser_order.status = LaserOrder.STATUS_NEEDS_MANUAL
        laser_order.error_message = f'Property-Parser: {exc}'
        laser_order.save(update_fields=['status', 'error_message'])

    return True


def _parse_iso(iso: str | None):
    if not iso:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso.replace('Z', '+00:00'))
    except Exception:
        return None

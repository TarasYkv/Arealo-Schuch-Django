"""Magvis Report-Mailer.

Versendet den Projekt-Abschluss-Report an die in MagvisReportConfig konfigurierte
E-Mail-Adresse. Nutzt das vorhandene Email-Backend (superconfig DB-basiert).
Inhaltsblöcke werden über Boolean-Flags gefiltert.
"""
from __future__ import annotations

import logging

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_project_report(project) -> bool:
    """Versendet Report für ein abgeschlossenes (oder fehlgeschlagenes) Projekt.

    Liefert True bei erfolgreichem Versand, False sonst.
    """
    from ..models import MagvisReportConfig

    user = project.user
    config = getattr(user, 'magvis_report_config', None) or MagvisReportConfig.objects.filter(user=user).first()
    if not config or not config.report_email:
        logger.info('Kein MagvisReportConfig — Report wird übersprungen')
        return False

    context = _build_context(project, config)
    html_body = render_to_string('magvis/emails/report.html', context)
    text_body = render_to_string('magvis/emails/report.txt', context)

    subject_template = config.subject_template or '[Magvis] {project_title} — fertig'
    subject = subject_template.format(project_title=project.title or project.topic or '–')

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@workloom.de'),
            to=[config.report_email],
            cc=config.cc_emails or None,
        )
        msg.attach_alternative(html_body, 'text/html')

        # Optional: Diagramm + Brainstorming inline anhängen
        if config.include_diagram_image and getattr(project, 'blog', None) and project.blog.diagram_image_path:
            _attach_image(msg, project.blog.diagram_image_path, 'diagram')
        if config.include_brainstorm_image and getattr(project, 'blog', None) and project.blog.brainstorm_image_path:
            _attach_image(msg, project.blog.brainstorm_image_path, 'brainstorm')

        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('Report-Mail an %s fehlgeschlagen', config.report_email)
        return False


def send_preflight_failure_alert(project, check_results: list) -> bool:
    """Versendet Alert-Email wenn Preflight-Stage scheitert.

    check_results: Liste von (name, ok, message)-Tupeln aus MagvisPreflightCheck.

    Liefert True bei erfolgreichem Versand. Nutzt MagvisReportConfig.report_email
    (auch wenn der eigentliche Report-Stage später ggf. nicht läuft).
    """
    from ..models import MagvisReportConfig
    user = project.user
    config = (getattr(user, 'magvis_report_config', None)
              or MagvisReportConfig.objects.filter(user=user).first())
    if not config or not config.report_email:
        logger.info('Kein MagvisReportConfig — Preflight-Alert übersprungen')
        return False

    failed = [r for r in check_results if not r[1]]
    failed_names = ', '.join(r[0] for r in failed)
    subject = f'⚠️ [Magvis] Preflight FAIL — {failed_names} ({project.topic[:40]})'

    lines = [
        f'Magvis-Preflight für Projekt "{project.topic}" hat fehlgeschlagen.',
        f'Project-ID: {project.id}',
        f'Stage: {project.stage}',
        '',
        'Ergebnisse aller Checks:',
    ]
    for name, ok, msg in check_results:
        tag = '✓' if ok else '✗'
        lines.append(f'  {tag} {name}: {msg}')
    lines += [
        '',
        'Pipeline wurde NICHT gestartet. Sobald die fehlgeschlagenen Services',
        'wieder verfügbar sind, kann der Run via /magvis/projekte/<id>/advance/',
        'oder automatisch durch den resume_unfinished_magvis_projects Beat-Task',
        '(alle 10 Min) fortgesetzt werden.',
    ]
    body = '\n'.join(lines)

    try:
        from django.core.mail import EmailMessage
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@workloom.de'),
            to=[config.report_email],
            cc=config.cc_emails or None,
        )
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Preflight-Alert-Mail an %s fehlgeschlagen', config.report_email)
        return False


def _attach_image(msg, rel_path: str, name: str) -> None:
    import os
    abs_path = rel_path if os.path.isabs(rel_path) else os.path.join(django_settings.MEDIA_ROOT, rel_path)
    if os.path.exists(abs_path):
        with open(abs_path, 'rb') as fh:
            msg.attach(f'magvis_{name}.png', fh.read(), 'image/png')


def _build_context(project, config) -> dict:
    """Stellt den Template-Kontext zusammen — gefiltert nach Config-Flags."""
    blog = getattr(project, 'blog', None)
    products = []
    if config.include_product_links:
        for p in (project.product_1, project.product_2):
            if not p:
                continue
            products.append({
                'title': p.title,
                'shopify_url': _product_url(p),
                'thumbnail_url': _featured_image_url(p) if config.include_product_thumbnails else '',
            })

    image_post_summary = []
    if config.include_image_post_summary:
        for asset in project.image_assets.all():
            for plat, st in (asset.posted_status or {}).items():
                if not isinstance(st, dict):
                    continue
                # Nur erfolgreich gepostete (mit URL UND success!=False)
                # zeigen — sonst landen falsche Erfolgs-Meldungen in der Email.
                url = st.get('url') or st.get('social_url') or ''
                success = st.get('success', None)
                if not url or success is False:
                    continue
                image_post_summary.append({
                    'image_title': asset.title_de or asset.source,
                    'platform': plat,
                    'url': url,
                })

    models_used, cost_breakdown, cost_sum = _collect_models_and_costs(project)

    coll = getattr(project, 'collection', None)
    return {
        'project': project,
        'config': config,
        'show_video_link': bool(config.include_video_link and project.posted_video),
        'video_link': _video_url(project),
        'show_youtube_link': bool(config.include_youtube_link and project.youtube_url),
        'youtube_url': project.youtube_url,
        # Alle Social-Plattform-URLs (IG/TikTok/YT) inkl. Fail-Status für den Report
        'video_socials': _video_socials(project),
        'show_blog_link': bool(config.include_blog_link and blog and blog.shopify_published_url),
        'blog_url': blog.shopify_published_url if blog else '',
        'show_blog_excerpt': bool(config.include_blog_excerpt and blog and blog.seo_description),
        'blog_excerpt': blog.seo_description if blog else '',
        'products': products,
        'show_collection': bool(coll and coll.shopify_collection_id),
        'collection_title': coll.title if coll else '',
        'collection_url': _collection_url(coll) if coll else '',
        'collection_was_existing': bool(coll and coll.was_existing),
        'collection_product_count': len(coll.assigned_product_ids or []) if coll else 0,
        'collection_short_desc': coll.short_description if coll else '',
        'show_diagram': bool(config.include_diagram_image and blog and blog.diagram_image_path),
        'show_brainstorm': bool(config.include_brainstorm_image and blog and blog.brainstorm_image_path),
        'image_post_summary': image_post_summary,
        # Modelle + Kosten — immer im Report (User-Wunsch)
        'models_used': models_used,
        'cost_breakdown': cost_breakdown,
        'cost_total_usd': f'{cost_sum:.3f}',
        'failed': project.stage == 'failed',
        'error_message': project.error_message,
    }


# Aktuelle Listenpreise (USD pro Bild bzw. pro 1M Tokens) — Stand 2026-04
_IMAGE_PRICES = {
    'gemini-2.5-flash-image': 0.039,             # Nano Banana
    'gemini-3.1-flash-image-preview': 0.067,     # Nano Banana 2
    'gemini-3-pro-image-preview': 0.135,         # Nano Banana Pro
}
_TEXT_PRICES_PER_1M = {
    # Input-Preis (Output liegt 2-4x höher; grobe Mischrechnung)
    'glm-4.5': 0.30, 'glm-4.6': 0.30, 'glm-5.1': 0.30,
    'claude-sonnet-4-5': 3.0, 'claude-opus-4-1': 15.0,
    'gpt-4o': 2.5, 'gpt-4o-mini': 0.15,
    'deepseek-chat': 0.28, 'deepseek-reasoner': 0.55,
}


def _collect_models_and_costs(project) -> tuple[list[dict], list[dict], float]:
    """Liest Settings + erzeugt Modell-/Kosten-Liste.

    Annahmen pro Standard-Run (kein perfektes Tracking, sondern Schaetzung):
    - 1 Title-Bild (Nano Banana)
    - 1 Diagramm + 1 Brainstorm (Nano Banana 2)
    - 8 KI-Produktbilder (4 pro Produkt × 2 Produkte; restliche 3 sind CDN, kostenlos)
    - Text-Generierung ~30k Tokens (Blog + Produkt-SEO)
    """
    from ..models import MagvisSettings

    s = MagvisSettings.objects.filter(user=project.user).first()
    text_model = (s.text_model if s and s.text_model else 'glm-5.1')
    text_provider = (s.text_provider if s and s.text_provider else 'zhipu')
    image_model = (s.gemini_image_model if s and s.gemini_image_model else 'gemini-2.5-flash-image')

    # Was wo verwendet wird
    models_used = [
        {'role': 'Blog- + Produkt-Texte', 'model': text_model, 'provider': text_provider},
        {'role': 'Hero-Titelbild', 'model': 'gemini-2.5-flash-image', 'provider': 'Gemini (Nano Banana)'},
        {'role': 'Diagramm + Brainstorming', 'model': 'gemini-3.1-flash-image-preview', 'provider': 'Gemini (Nano Banana 2)'},
        {'role': 'Produktbilder (Topf+Gravur)', 'model': image_model, 'provider': 'Gemini'},
    ]

    # Kostenschätzung
    cost_breakdown = []

    # 1 Title-Bild
    p_title = _IMAGE_PRICES.get('gemini-2.5-flash-image', 0.04)
    cost_breakdown.append({'item': 'Hero-Titelbild (1×)', 'model': 'Nano Banana', 'cost': p_title})

    # 2 Bilder Diagram + Brainstorm
    p_nb2 = _IMAGE_PRICES.get('gemini-3.1-flash-image-preview', 0.07)
    cost_breakdown.append({'item': 'Diagramm + Brainstorming (2×)', 'model': 'Nano Banana 2', 'cost': 2 * p_nb2})

    # 8 Produkt-KI-Bilder (4 KI × 2 Produkte) — Modell wie image_model gesetzt
    p_prod = _IMAGE_PRICES.get(image_model, p_nb2)
    n_prod = 4 * (1 if project.product_1 else 0) + 4 * (1 if project.product_2 else 0)
    if n_prod:
        cost_breakdown.append({
            'item': f'Produktbilder ({n_prod}×)',
            'model': 'Nano Banana 2' if image_model == 'gemini-3.1-flash-image-preview' else image_model,
            'cost': n_prod * p_prod,
        })

    # Text — grobe 30k Token Schätzung (input+output gemischt)
    p_txt = _TEXT_PRICES_PER_1M.get(text_model.lower(), 0.30)
    cost_breakdown.append({
        'item': 'Texte (~30k Tokens, Schätzung)',
        'model': text_model,
        'cost': 30_000 / 1_000_000 * p_txt,
    })

    cost_sum = sum(item['cost'] for item in cost_breakdown)
    # Strings für Template
    for item in cost_breakdown:
        item['cost_str'] = f'${item["cost"]:.3f}'
    return models_used, cost_breakdown, cost_sum


def _product_url(product) -> str:
    """Liefert öffentliche Produkt-URL (NIE admin-Link).

    Falls product.handle fehlt, hole es per Shopify-API.
    Falls custom_domain leer, mappe naturkind-de.myshopify.com → naturmacher.de.
    """
    store = getattr(product, 'shopify_store', None)
    if not store or not getattr(product, 'shopify_product_id', None):
        return ''
    handle = getattr(product, 'handle', '') or getattr(product, 'shopify_handle', '') or ''
    if not handle:
        try:
            import requests as _rq
            r = _rq.get(
                f'https://{store.shop_domain}/admin/api/2023-10/products/{product.shopify_product_id}.json',
                headers={'X-Shopify-Access-Token': store.access_token},
                timeout=10,
            )
            if r.status_code == 200:
                handle = r.json().get('product', {}).get('handle', '')
        except Exception:
            pass
    if not handle:
        return f'https://{store.shop_domain}/products/{product.shopify_product_id}'
    domain = (getattr(store, 'custom_domain', None)
              or _public_domain_for(store.shop_domain))
    return f'https://{domain}/products/{handle}'


def _public_domain_for(shop_domain: str) -> str:
    """Mappt Shopify-Backend-Domain → öffentliche Custom-Domain."""
    mapping = {
        'naturkind-de.myshopify.com': 'naturmacher.de',
    }
    return mapping.get(shop_domain, shop_domain)


def _collection_url(collection) -> str:
    """Liefert öffentliche Collection-URL."""
    if not collection or not collection.shopify_handle:
        return collection.shopify_url if collection else ''
    # Aus dem ploom-Store custom_domain ableiten
    try:
        from ploom.models import PLoomSettings
        ps = PLoomSettings.objects.filter(user=collection.project.user).first()
        if ps and ps.default_store:
            domain = (getattr(ps.default_store, 'custom_domain', None)
                      or _public_domain_for(ps.default_store.shop_domain))
            return f'https://{domain}/collections/{collection.shopify_handle}'
    except Exception:
        pass
    return collection.shopify_url


def _featured_image_url(product) -> str:
    img = product.images.filter(is_featured=True).first() or product.images.first()
    if not img:
        return ''
    if img.image:
        return img.image.url
    return img.external_url or ''


def _video_url(project) -> str:
    if not project.posted_video:
        return ''
    v = project.posted_video
    try:
        return v.video_file.url
    except Exception:
        return ''


def _video_socials(project) -> list[dict]:
    """Liefert pro Plattform Status für den Report — auch Fails sind sichtbar.

    Format: [{'platform': 'YouTube', 'url': '...', 'success': True, 'error': ''}, ...]
    Reihenfolge YouTube → Instagram → TikTok (= übliche Wichtigkeit).
    """
    if not project.posted_video:
        return []
    v = project.posted_video
    posted_urls = v.social_posted_urls or {}
    requested = (v.social_platforms_posted or '').split(',')
    requested = [p.strip().lower() for p in requested if p.strip()]
    error_blob = v.social_post_error or ''
    # social_post_error ist JSON {platform: error} (siehe social_pipeline.py)
    import json as _json
    err_map = {}
    try:
        err_map = _json.loads(error_blob) if error_blob.startswith('{') else {}
    except Exception:
        pass

    LABELS = {'youtube': 'YouTube', 'instagram': 'Instagram', 'tiktok': 'TikTok',
              'facebook': 'Facebook', 'pinterest': 'Pinterest'}
    out: list[dict] = []
    seen = set()
    for plat in ['youtube', 'instagram', 'tiktok'] + requested:
        if plat in seen:
            continue
        seen.add(plat)
        url = posted_urls.get(plat, '')
        out.append({
            'platform': LABELS.get(plat, plat.title()),
            'platform_key': plat,
            'url': url,
            'success': bool(url),
            'error': err_map.get(plat, '') if not url else '',
            'requested': plat in requested,
        })
    # Filter: nur die, die requested oder url haben (sonst leeres Geräusch)
    return [o for o in out if o['requested'] or o['url']]

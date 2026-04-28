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
                if isinstance(st, dict) and st.get('url'):
                    image_post_summary.append({
                        'image_title': asset.title_de or asset.source,
                        'platform': plat,
                        'url': st.get('url', ''),
                    })

    return {
        'project': project,
        'config': config,
        'show_video_link': bool(config.include_video_link and project.posted_video),
        'video_link': _video_url(project),
        'show_youtube_link': bool(config.include_youtube_link and project.youtube_url),
        'youtube_url': project.youtube_url,
        'show_blog_link': bool(config.include_blog_link and blog and blog.shopify_published_url),
        'blog_url': blog.shopify_published_url if blog else '',
        'show_blog_excerpt': bool(config.include_blog_excerpt and blog and blog.seo_description),
        'blog_excerpt': blog.seo_description if blog else '',
        'products': products,
        'show_diagram': bool(config.include_diagram_image and blog and blog.diagram_image_path),
        'show_brainstorm': bool(config.include_brainstorm_image and blog and blog.brainstorm_image_path),
        'image_post_summary': image_post_summary,
        'show_costs': bool(config.include_costs),
        'cost_total': str(project.cost_total or 0),
        'failed': project.stage == 'failed',
        'error_message': project.error_message,
    }


def _product_url(product) -> str:
    store = getattr(product, 'shopify_store', None)
    handle = getattr(product, 'handle', '') or ''
    if store and handle:
        return f'https://{store.custom_domain or store.shop_domain}/products/{handle}'
    if store and getattr(product, 'shopify_product_id', ''):
        return f'https://{store.shop_domain}/admin/products/{product.shopify_product_id}'
    return ''


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

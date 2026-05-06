"""Lasergravur-Views — Liste, Editor, Live-Preview, Download."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import (
    LaserOrder, LaserDesign, LaserSettings,
    FONT_CHOICES, ALIGN_H_CHOICES, ALIGN_V_CHOICES,
)

logger = logging.getLogger(__name__)


def _is_staff(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _is_staff(self.request.user)


class OrderListView(StaffRequiredMixin, ListView):
    model = LaserOrder
    template_name = 'lasergravur/order_list.html'
    context_object_name = 'orders'
    paginate_by = 50

    DONE_STATUSES = ('engraved', 'downloaded')  # erledigt → standardmäßig ausblenden

    def get_queryset(self):
        qs = LaserOrder.objects.filter(user=self.request.user)
        status = self.request.GET.get('status')
        if status == '__all__':
            pass  # alle anzeigen
        elif status:
            qs = qs.filter(status=status)
        else:
            # Default: nur offene Bestellungen (noch zu bearbeiten)
            qs = qs.exclude(status__in=self.DONE_STATUSES)
        return qs.select_related('design').order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['status_choices'] = LaserOrder.STATUS_CHOICES
        ctx['status_counts'] = {
            s[0]: LaserOrder.objects.filter(user=self.request.user, status=s[0]).count()
            for s in LaserOrder.STATUS_CHOICES
        }
        ctx['open_count'] = (LaserOrder.objects.filter(user=self.request.user)
                              .exclude(status__in=self.DONE_STATUSES).count())
        ctx['total_count'] = LaserOrder.objects.filter(user=self.request.user).count()
        return ctx


@login_required
@user_passes_test(_is_staff)
def order_editor(request, pk):
    """Editor-View für ein Magvis-Auftrag — zeigt Live-Preview + Form."""
    from .models import TOPF_MODELS
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    design, _ = LaserDesign.objects.get_or_create(order=order)
    # Icon-Library für Picker (aus Asset-Loader)
    icon_choices = _get_icon_choices(request.user, order.topf_model)

    return render(request, 'lasergravur/order_editor.html', {
        'order': order,
        'design': design,
        'font_choices': FONT_CHOICES,
        'align_h_choices': ALIGN_H_CHOICES,
        'align_v_choices': ALIGN_V_CHOICES,
        'icon_choices': icon_choices,
    })


def _get_icon_choices(user, topf_model: str) -> list:
    """Liefert Liste [(id, label), ...] aller verfügbaren Icons.

    Nutzt den asset_loader-Cache; lädt einmal von Shopify wenn nicht da.
    """
    from .renderers.asset_loader import ensure_assets
    settings_obj = LaserSettings.objects.filter(user=user).first()
    if not settings_obj or not settings_obj.shopify_store:
        return []
    try:
        config = ensure_assets(settings_obj.shopify_store, topf_model)
    except Exception as exc:
        logger.warning('Icon-Choices: %s', exc)
        return []
    icon_paths = config.get('iconPaths') or {}
    # Keys aus JSON-Cache sind strings → in int sortiert
    nums = []
    for k in icon_paths.keys():
        try:
            nums.append(int(k))
        except Exception:
            pass
    nums.sort()
    return [(n, f'Icon {n}') for n in nums]


@login_required
@user_passes_test(_is_staff)
def order_preview_png(request, pk):
    """Liefert das aktuell gerenderte Preview-PNG (mit Topf-Hintergrund)."""
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    design = order.design
    settings_obj = LaserSettings.objects.filter(user=request.user).first()
    if not settings_obj or not settings_obj.shopify_store:
        return HttpResponse(status=400, content=b'No store configured')
    try:
        png = _render_for(order, design, settings_obj.shopify_store, with_background=True)
    except Exception as exc:
        logger.exception('Preview-Render')
        return HttpResponse(status=500, content=str(exc).encode())
    resp = HttpResponse(png, content_type='image/png')
    resp['Cache-Control'] = 'no-store'
    return resp


def _render_for(order, design, store, *, with_background: bool, output_size_px: int = None):
    """Dispatcht zum richtigen Renderer pro Topf-Modell."""
    if output_size_px is None:
        # Preview = 800px (Shop-Format), Export = passend zu Gravur-Größe
        if with_background:
            output_size_px = 800
        else:
            cm_w, _ = order.gravur_size_cm
            output_size_px = int(cm_w / 2.54 * 300)  # 300 DPI

    # Fotogravur: Kunden-Bild aus Properties + optional Text
    if order.topf_model == 'fotogravur':
        from .renderers.fotogravur import render_fotogravur
        return render_fotogravur(order, design, store,
                                  with_background=with_background,
                                  output_size_px=output_size_px,
                                  topf_model=order.topf_model)

    # Hochzeit-Schema (vornamen + optional datum + motiv) — Hochzeit, Hochzeit Glossy,
    # Glossy Geburt, Mini Palm (nur 1 Textfeld + Motiv).
    if order.topf_model in ('hochzeit', 'hochzeit_glossy', 'glossy_geburt', 'minipalm'):
        from .renderers.hochzeit import render_hochzeit
        return render_hochzeit(order, design, store,
                                with_background=with_background,
                                output_size_px=output_size_px,
                                topf_model=order.topf_model)
    # Designer + Glossy + Mini Solo + Mini Palm + Glossywhite + Fotogravur + Birthtree + Unknown
    # → generischer Renderer (4 Textzeilen + Schrift + Icon)
    from .renderers.designer import render_designer
    return render_designer(order, design, store,
                            with_background=with_background,
                            output_size_px=output_size_px,
                            topf_model=order.topf_model)


@login_required
@user_passes_test(_is_staff)
@require_POST
def order_save(request, pk):
    """Speichert die Design-Felder (vom Editor-Form). HTMX-Endpoint."""
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    design, _ = LaserDesign.objects.get_or_create(order=order)

    design.text_1 = request.POST.get('text_1', '')[:200]
    design.text_2 = request.POST.get('text_2', '')[:200]
    design.text_3 = request.POST.get('text_3', '')[:200]
    design.text_4 = request.POST.get('text_4', '')[:200]
    design.font = request.POST.get('font', design.font or 'Allura')
    icon_id_raw = request.POST.get('icon_id', '').strip()
    design.icon_id = int(icon_id_raw) if icon_id_raw.isdigit() else None
    try:
        design.font_size_pt = int(request.POST.get('font_size_pt', design.font_size_pt or 48))
    except Exception:
        pass
    design.alignment_h = request.POST.get('alignment_h', design.alignment_h or 'center')
    design.alignment_v = request.POST.get('alignment_v', design.alignment_v or 'center')
    try:
        design.offset_x_mm = float(request.POST.get('offset_x_mm', design.offset_x_mm or 0))
    except Exception:
        pass
    try:
        design.offset_y_mm = float(request.POST.get('offset_y_mm', design.offset_y_mm or 0))
    except Exception:
        pass
    design.save()

    # Confirm-Action
    if request.POST.get('action') == 'confirm':
        order.status = LaserOrder.STATUS_CONFIRMED
        order.confirmed_at = timezone.now()
        order.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        # Status-Tag zurück nach Shopify
        try:
            from .services.shopify_tagger import add_tag_to_order
            add_tag_to_order(request.user, order.shopify_order_id, 'lasergravur_designed')
        except Exception as exc:
            logger.warning('Shopify-Tag-Sync (designed): %s', exc)
        return redirect('lasergravur:order_download_png', pk=order.pk)

    # HTMX returns nur den preview-Container
    if request.headers.get('HX-Request'):
        from django.urls import reverse
        ts = int(timezone.now().timestamp())
        url = reverse('lasergravur:order_preview_png', args=[order.pk]) + f'?t={ts}'
        return HttpResponse(
            f'<img id="preview-img" src="{url}" '
            f'style="max-width:100%;border-radius:8px;" alt="Live-Preview">'
        )
    return redirect('lasergravur:order_editor', pk=order.pk)


@login_required
@user_passes_test(_is_staff)
def order_download_png(request, pk):
    """Liefert das hochauflösende Lasergravur-PNG zum Download."""
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    design = order.design
    settings_obj = LaserSettings.objects.filter(user=request.user).first()
    if not settings_obj or not settings_obj.shopify_store:
        return HttpResponse(status=400, content=b'No store')
    try:
        png = _render_for(order, design, settings_obj.shopify_store,
                           with_background=False)
    except Exception as exc:
        logger.exception('Download-Render')
        return HttpResponse(status=500, content=str(exc).encode())

    # Status auf 'downloaded'
    order.status = LaserOrder.STATUS_DOWNLOADED
    order.downloaded_at = timezone.now()
    order.save(update_fields=['status', 'downloaded_at', 'updated_at'])

    fname = f'lasergravur_{order.shopify_order_number or order.id.hex[:8]}.png'
    resp = HttpResponse(png, content_type='image/png')
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@login_required
@user_passes_test(_is_staff)
@require_POST
def order_change_status(request, pk):
    """Ändert den Status manuell auf einen beliebigen Wert.

    Wenn neuer Status 'engraved' → automatischer Shopify-Tag.
    """
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    new_status = request.POST.get('status', '').strip()
    valid = {s[0] for s in LaserOrder.STATUS_CHOICES}
    if new_status not in valid:
        messages.error(request, f'Ungültiger Status: {new_status}')
    else:
        old = order.status
        order.status = new_status
        # Zeitstempel je nach Status setzen
        if new_status == LaserOrder.STATUS_CONFIRMED and not order.confirmed_at:
            order.confirmed_at = timezone.now()
        elif new_status == LaserOrder.STATUS_DOWNLOADED and not order.downloaded_at:
            order.downloaded_at = timezone.now()
        elif new_status == LaserOrder.STATUS_ENGRAVED and not order.engraved_at:
            order.engraved_at = timezone.now()
        order.save()
        # Shopify-Tag bei engraved
        if new_status == LaserOrder.STATUS_ENGRAVED:
            try:
                from .services.shopify_tagger import add_tag_to_order
                add_tag_to_order(request.user, order.shopify_order_id, 'lasergravur_engraved')
            except Exception as exc:
                logger.warning('Shopify-Tag bei Status-Change: %s', exc)
        messages.success(request, f'#{order.shopify_order_number}: {old} → {new_status}')
    # Redirect zurück (entweder Liste oder Editor)
    next_url = request.POST.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect('lasergravur:order_list')


@login_required
@user_passes_test(_is_staff)
@require_POST
def order_mark_engraved(request, pk):
    """Markiert die Bestellung als graviert (Mitarbeiter-Click nach Lasergravur)."""
    order = get_object_or_404(LaserOrder, pk=pk, user=request.user)
    order.status = LaserOrder.STATUS_ENGRAVED
    order.engraved_at = timezone.now()
    order.save(update_fields=['status', 'engraved_at', 'updated_at'])
    # Status-Tag zurück nach Shopify
    try:
        from .services.shopify_tagger import add_tag_to_order
        add_tag_to_order(request.user, order.shopify_order_id, 'lasergravur_engraved')
    except Exception as exc:
        logger.warning('Shopify-Tag-Sync (engraved): %s', exc)
    messages.success(request, f'Bestellung #{order.shopify_order_number} als graviert markiert.')
    return redirect('lasergravur:order_list')

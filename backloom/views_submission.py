"""Views fuer die Submission-Pipeline (Phase 5).

- SubmissionDashboardView: Liste aller SubmissionAttempts mit Status-Filter
- SubmissionLiveView: Detail-Seite mit noVNC iframe + Step-Log + Live-Status
- API-Endpoints fuer Trigger / Status / Skip / Pause
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView

from .models import (
    BacklinkSource,
    NaturmacherProfile,
    SubmissionAttempt,
    SubmissionAttemptStatus,
)

logger = logging.getLogger(__name__)


class SubmissionDashboardView(LoginRequiredMixin, ListView):
    """Liste aller SubmissionAttempts des angemeldeten Users.

    Auf einen Blick:
      - Status (Badge),
      - Source-Domain,
      - Dauer,
      - Backlink-URL falls vorhanden,
      - Buttons: Live-View | Re-Run | Source oeffnen
    """
    model = SubmissionAttempt
    template_name = 'backloom/submission_dashboard.html'
    context_object_name = 'attempts'
    paginate_by = 25

    def get_queryset(self):
        qs = SubmissionAttempt.objects.select_related(
            'source', 'profile', 'bio_variant',
        ).order_by('-created_at')

        # User darf nur eigene sehen (Profil-bezogen). Superuser alle.
        if not self.request.user.is_superuser:
            qs = qs.filter(profile__user=self.request.user)

        # Filter aus URL-Params
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        domain = self.request.GET.get('domain', '').strip()
        if domain:
            qs = qs.filter(source__domain__icontains=domain)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Status-Counts fuer die Filter-Pills
        from django.db.models import Count
        base = SubmissionAttempt.objects.all()
        if not self.request.user.is_superuser:
            base = base.filter(profile__user=self.request.user)
        ctx['status_counts'] = dict(
            base.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
        )
        ctx['active_status'] = self.request.GET.get('status', '')
        ctx['active_domain'] = self.request.GET.get('domain', '')
        ctx['status_choices'] = SubmissionAttemptStatus.choices

        # Aktuell-laufende Sessions (fuer "Live"-Banner)
        ctx['running_attempts'] = base.filter(
            status__in=[SubmissionAttemptStatus.RUNNING,
                        SubmissionAttemptStatus.NEEDS_MANUAL],
        ).order_by('-started_at')[:5]

        # Quick-Stats fuer Header
        ctx['stats'] = {
            'total': base.count(),
            'success': base.filter(status=SubmissionAttemptStatus.SUCCESS).count(),
            'manual': base.filter(status=SubmissionAttemptStatus.NEEDS_MANUAL).count(),
            'failed': base.filter(status__in=[
                SubmissionAttemptStatus.FAILED_CAPTCHA,
                SubmissionAttemptStatus.FAILED_OTHER,
            ]).count(),
        }
        return ctx


class SubmissionLiveView(LoginRequiredMixin, DetailView):
    """Detail-Seite eines Submission-Attempts mit Live-Browser (noVNC) + Step-Log."""
    model = SubmissionAttempt
    template_name = 'backloom/submission_live.html'
    context_object_name = 'attempt'

    def get_queryset(self):
        qs = SubmissionAttempt.objects.select_related(
            'source', 'profile', 'bio_variant',
        )
        if not self.request.user.is_superuser:
            qs = qs.filter(profile__user=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .services.browser_client import BrowserContainerClient
        ctx['novnc_url'] = self.object.novnc_url or BrowserContainerClient.public_novnc_url()
        return ctx


# --------------------------------------------------------------------------
# API-Endpoints
# --------------------------------------------------------------------------


@login_required
@require_POST
def api_start_submission(request):
    """Startet eine neue Submission per AJAX.

    Body:
      source_id: UUID der BacklinkSource
    """
    import json
    try:
        body = json.loads(request.body)
    except Exception:
        body = request.POST
    source_id = body.get('source_id', '')
    if not source_id:
        return JsonResponse({'ok': False, 'error': 'source_id fehlt'}, status=400)

    try:
        source = BacklinkSource.objects.get(pk=source_id)
    except BacklinkSource.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Source nicht gefunden'}, status=404)

    try:
        profile = NaturmacherProfile.objects.get(user=request.user)
    except NaturmacherProfile.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Du hast kein NaturmacherProfile. Lege es im Admin an.'
        }, status=400)

    # Skip wenn schon laufend
    running = source.submission_attempts.filter(status__in=[
        SubmissionAttemptStatus.QUEUED,
        SubmissionAttemptStatus.RUNNING,
    ]).first()
    if running:
        return JsonResponse({'ok': False, 'error': 'Source hat schon laufenden Attempt',
                              'attempt_id': str(running.id)}, status=409)

    from .tasks import submit_backlink_task
    task = submit_backlink_task.delay(source_id=str(source.id), profile_id=profile.id)
    return JsonResponse({
        'ok': True,
        'task_id': task.id,
        'source': {'id': str(source.id), 'domain': source.domain},
    })


@login_required
@require_GET
def api_attempt_status(request, attempt_id):
    """Polling-Endpoint fuer die Live-View. Liefert aktuellen Status + neue Step-Logs."""
    try:
        a = SubmissionAttempt.objects.select_related('source').get(pk=attempt_id)
    except SubmissionAttempt.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    if not request.user.is_superuser and a.profile.user_id != request.user.id:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    # Optional: ?since=N (Index in step_log) → nur neue Schritte zurueck
    try:
        since = int(request.GET.get('since', '0'))
    except ValueError:
        since = 0
    full_log = a.step_log or []
    new_steps = full_log[since:]

    return JsonResponse({
        'ok': True,
        'status': a.status,
        'status_display': a.get_status_display(),
        'is_terminal': a.status in [
            SubmissionAttemptStatus.SUCCESS,
            SubmissionAttemptStatus.FAILED_CAPTCHA,
            SubmissionAttemptStatus.FAILED_OTHER,
            SubmissionAttemptStatus.SKIPPED,
        ],
        'duration_s': a.duration_seconds,
        'backlink_url': a.backlink_url,
        'is_dofollow': a.is_dofollow,
        'novnc_url': a.novnc_url,
        'anchor_text': a.anchor_text_used,
        'cost_eur': str(a.cost_eur),
        'error_message': a.error_message,
        'total_steps': len(full_log),
        'steps': new_steps,
    })


@login_required
@require_GET
def api_source_search(request):
    """Sucht BacklinkSources fuer das Submit-Modal."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'ok': True, 'results': []})
    qs = BacklinkSource.objects.filter(domain__icontains=q).order_by(
        'is_processed', '-quality_score',
    )[:15]
    return JsonResponse({
        'ok': True,
        'results': [
            {
                'id': str(s.id),
                'domain': s.domain,
                'url': s.url,
                'title': s.title or '',
                'category': s.get_category_display(),
                'is_processed': s.is_processed,
                'quality_score': s.quality_score,
            } for s in qs
        ],
    })


@login_required
@require_POST
def api_attempt_skip(request, attempt_id):
    """Markiert einen Attempt als geskippt (User-Override)."""
    a = get_object_or_404(SubmissionAttempt, pk=attempt_id)
    if not request.user.is_superuser and a.profile.user_id != request.user.id:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    if a.status not in [SubmissionAttemptStatus.NEEDS_MANUAL,
                        SubmissionAttemptStatus.QUEUED,
                        SubmissionAttemptStatus.RUNNING]:
        return JsonResponse({'ok': False, 'error': f'kann von {a.status} nicht skippen'},
                              status=400)
    a.status = SubmissionAttemptStatus.SKIPPED
    a.save(update_fields=['status', 'updated_at'])
    a.add_step('Vom User uebersprungen', level='warn')
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_attempt_mark_success(request, attempt_id):
    """User markiert manuell, dass die Submission erfolgreich war.

    Setzt Status -> SUCCESS, optional backlink_url + Notiz aus Body.
    Bricht damit den Wait-Loop des BotRunners (sofern aktiv) und beendet
    die Browser-Session.
    """
    import json
    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}
    a = get_object_or_404(SubmissionAttempt, pk=attempt_id)
    if not request.user.is_superuser and a.profile.user_id != request.user.id:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    if a.status not in [SubmissionAttemptStatus.NEEDS_MANUAL,
                        SubmissionAttemptStatus.RUNNING]:
        return JsonResponse({'ok': False, 'error': f'kann von {a.status} nicht success'},
                              status=400)

    backlink_url = (body.get('backlink_url') or '').strip()
    note = (body.get('note') or '').strip()

    a.status = SubmissionAttemptStatus.SUCCESS
    if backlink_url:
        a.backlink_url = backlink_url
    a.save(update_fields=['status', 'backlink_url', 'updated_at'])
    a.add_step(
        f'Manuell als ERFOLGREICH markiert' + (f' — {note}' if note else ''),
        level='info',
    )
    return JsonResponse({'ok': True, 'status': a.status, 'backlink_url': a.backlink_url})


@login_required
@require_POST
def api_attempt_resume(request, attempt_id):
    """User signalisiert: Bot soll weiter machen (z.B. nach manuellem Captcha-Loesen).

    Setzt Status zurueck auf RUNNING. Der Wait-Loop im BotRunner bricht ab
    und der Captcha-Cascade-Callback faehrt weiter im Agent-Schleifen-Loop.
    """
    a = get_object_or_404(SubmissionAttempt, pk=attempt_id)
    if not request.user.is_superuser and a.profile.user_id != request.user.id:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    if a.status != SubmissionAttemptStatus.NEEDS_MANUAL:
        return JsonResponse({'ok': False, 'error': f'kann von {a.status} nicht resume'},
                              status=400)
    a.status = SubmissionAttemptStatus.RUNNING
    a.save(update_fields=['status', 'updated_at'])
    a.add_step('User: Bot soll weitermachen', level='info')
    return JsonResponse({'ok': True})

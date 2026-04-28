"""Wizard-HTML-Views für Magvis (function-based, blogprep-Stil)."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    MagvisSettingsForm,
    ProjectStartForm,
    ReportConfigForm,
    TopicQueueForm,
)
from .models import (
    MagvisImageAsset,
    MagvisProject,
    MagvisReportConfig,
    MagvisSettings,
    MagvisTopicQueue,
)

logger = logging.getLogger(__name__)


@login_required
def project_list(request):
    qs = MagvisProject.objects.filter(user=request.user)
    queue_count = MagvisTopicQueue.objects.filter(
        user=request.user, status=MagvisTopicQueue.STATUS_PENDING
    ).count()
    return render(request, 'magvis/project_list.html', {
        'projects': qs[:50],
        'pending_topic_count': queue_count,
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectStartForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data

            if cleaned.get('use_queue'):
                item = MagvisTopicQueue.pop_next(request.user)
                if not item:
                    messages.error(request, 'Themen-Queue ist leer.')
                    return redirect('magvis:project_create')
                project = MagvisProject.objects.create(
                    user=request.user,
                    title=item.topic[:255],
                    topic=item.topic,
                    keywords=item.keywords,
                    target_audience=item.target_audience,
                    scheduled_at=cleaned.get('scheduled_at'),
                    auto_advance=cleaned.get('auto_advance', True),
                    source_queue_item=item,
                )
            else:
                project = form.save(commit=False)
                project.user = request.user
                project.keywords = cleaned.get('keywords', [])
                project.save()

            if project.scheduled_at and project.scheduled_at > timezone.now():
                from .tasks import schedule_project
                schedule_project(project)
                messages.success(request, f'Projekt für {project.scheduled_at:%d.%m.%Y %H:%M} eingeplant.')
            elif project.auto_advance:
                from .tasks import run_full_chain
                run_full_chain.delay(str(project.id))
                messages.success(request, 'Projekt erstellt — Pipeline läuft im Hintergrund.')
            return redirect('magvis:project_detail', project_id=project.id)
    else:
        form = ProjectStartForm()
    return render(request, 'magvis/project_create.html', {'form': form})


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(MagvisProject, id=project_id, user=request.user)
    blog = getattr(project, 'blog', None)
    assets = project.image_assets.all().order_by('source', 'id')
    return render(request, 'magvis/project_detail.html', {
        'project': project, 'blog': blog, 'assets': assets,
    })


@login_required
@require_POST
def project_advance(request, project_id):
    project = get_object_or_404(MagvisProject, id=project_id, user=request.user)
    slug = project.next_stage_slug()
    if not slug:
        return JsonResponse({'error': 'Kein nächster Stage'}, status=400)
    from .tasks import run_stage_async
    result = run_stage_async.delay(str(project.id), slug)
    return JsonResponse({'task_id': result.id, 'stage': slug})


@login_required
def project_status(request, project_id):
    project = get_object_or_404(MagvisProject, id=project_id, user=request.user)
    return JsonResponse({
        'stage': project.stage, 'progress_pct': project.progress_pct,
        'error_message': project.error_message,
        'youtube_url': project.youtube_url,
        'product_1_id': project.product_1_id, 'product_2_id': project.product_2_id,
    })


# --- Settings + Report ----------------------------------------------------

@login_required
def settings_view(request):
    obj, _ = MagvisSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = MagvisSettingsForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Magvis-Einstellungen gespeichert.')
            return redirect('magvis:settings')
    else:
        form = MagvisSettingsForm(instance=obj)
    return render(request, 'magvis/settings.html', {'form': form, 'settings': obj})


@login_required
def report_config_view(request):
    obj, _ = MagvisReportConfig.objects.get_or_create(
        user=request.user, defaults={'report_email': request.user.email or ''}
    )
    if request.method == 'POST':
        form = ReportConfigForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Report-Konfiguration gespeichert.')
            return redirect('magvis:report_config')
    else:
        form = ReportConfigForm(instance=obj)
    return render(request, 'magvis/report_config.html', {'form': form})


# --- Themen-Queue ---------------------------------------------------------

@login_required
def topics_list(request):
    qs = MagvisTopicQueue.objects.filter(user=request.user)
    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'magvis/topics/list.html', {
        'topics': qs,
        'status_filter': status_filter,
    })


@login_required
def topic_create(request):
    if request.method == 'POST':
        form = TopicQueueForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            messages.success(request, 'Topic gespeichert.')
            return redirect('magvis:topics_list')
    else:
        form = TopicQueueForm()
    return render(request, 'magvis/topics/edit.html', {'form': form})


@login_required
def topic_edit(request, topic_id):
    obj = get_object_or_404(MagvisTopicQueue, id=topic_id, user=request.user)
    if request.method == 'POST':
        form = TopicQueueForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('magvis:topics_list')
    else:
        form = TopicQueueForm(instance=obj)
    return render(request, 'magvis/topics/edit.html', {'form': form, 'topic': obj})


@login_required
@require_POST
def topic_delete(request, topic_id):
    obj = get_object_or_404(MagvisTopicQueue, id=topic_id, user=request.user)
    obj.delete()
    return redirect('magvis:topics_list')


@login_required
def topic_bulk_import(request):
    if request.method == 'POST':
        text = request.POST.get('topics_text', '')
        priority_default = int(request.POST.get('priority', 100) or 100)
        created = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: "topic" oder "topic;keyword1,keyword2;priority"
            parts = line.split(';')
            topic = parts[0].strip()
            keywords = []
            priority = priority_default
            if len(parts) > 1:
                keywords = [k.strip() for k in parts[1].split(',') if k.strip()]
            if len(parts) > 2:
                try:
                    priority = int(parts[2].strip())
                except ValueError:
                    pass
            MagvisTopicQueue.objects.create(
                user=request.user, topic=topic, keywords=keywords, priority=priority,
            )
            created += 1
        messages.success(request, f'{created} Topics importiert.')
        return redirect('magvis:topics_list')
    return render(request, 'magvis/topics/bulk_import.html')


# --- Bild-Posten (Schritt 5 Wizard) --------------------------------------

@login_required
@require_POST
def image_post(request, project_id, asset_id):
    project = get_object_or_404(MagvisProject, id=project_id, user=request.user)
    asset = get_object_or_404(MagvisImageAsset, id=asset_id, project=project)
    platforms = request.POST.getlist('platforms')
    use_overlay = request.POST.get('use_overlay') == 'on'
    overlay_text = request.POST.get('overlay_text', '').strip()
    overlay_method = request.POST.get('overlay_method', 'pil')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()

    from .tasks import post_image_async
    result = post_image_async.delay(
        asset.id, platforms, use_overlay, overlay_text, overlay_method, title, description,
    )
    return JsonResponse({'task_id': result.id})

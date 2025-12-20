"""
VSkript Views

Dashboard, Create, Detail und API-Endpunkte für Videoskript-Generierung.
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator

from .models import (
    VSkriptProject,
    VSkriptGenerationLog,
    SCRIPT_TYPE_CHOICES,
    TONE_CHOICES,
    TARGET_AUDIENCE_CHOICES,
    PLATFORM_CHOICES,
    DURATION_CHOICES,
    AI_MODEL_CHOICES
)
from .services import VSkriptService


@login_required
def dashboard(request):
    """Übersicht aller VSkript Projekte"""
    projects = VSkriptProject.objects.filter(user=request.user).order_by('-created_at')

    # Pagination
    paginator = Paginator(projects, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiken
    total_projects = projects.count()
    total_words = sum(p.word_count for p in projects)

    context = {
        'page_obj': page_obj,
        'total_projects': total_projects,
        'total_words': total_words,
    }

    return render(request, 'vskript/dashboard.html', context)


@login_required
def project_create(request):
    """Neues Skript erstellen"""
    context = {
        'script_types': SCRIPT_TYPE_CHOICES,
        'tones': TONE_CHOICES,
        'target_audiences': TARGET_AUDIENCE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'durations': DURATION_CHOICES,
        'ai_models': AI_MODEL_CHOICES,
    }

    if request.method == 'POST':
        # Projekt erstellen
        keyword = request.POST.get('keyword', '').strip()
        description = request.POST.get('description', '').strip()
        script_type = request.POST.get('script_type', 'interesting_facts')
        tone = request.POST.get('tone', 'casual')
        target_audience = request.POST.get('target_audience', 'general')
        platform = request.POST.get('platform', 'youtube')
        duration = float(request.POST.get('duration', 1.0))
        ai_model = request.POST.get('ai_model', 'gpt-5')

        if not keyword:
            messages.error(request, 'Bitte gib ein Keyword/Thema ein.')
            return render(request, 'vskript/create.html', context)

        # Projekt erstellen (Skript wird per AJAX generiert)
        project = VSkriptProject.objects.create(
            user=request.user,
            title=keyword[:200],
            keyword=keyword,
            description=description,
            script_type=script_type,
            tone=tone,
            target_audience=target_audience,
            platform=platform,
            duration=duration,
            ai_model=ai_model
        )

        return redirect('vskript:detail', project_id=project.id)

    return render(request, 'vskript/create.html', context)


@login_required
def project_detail(request, project_id):
    """Skript ansehen und bearbeiten"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_script':
            # Manuell bearbeitetes Skript speichern
            project.script = request.POST.get('script', '')
            project.word_count = len(project.script.split())
            project.estimated_duration = round(project.word_count / 130, 1)
            project.save()
            messages.success(request, 'Skript gespeichert!')

        elif action == 'update_settings':
            # Einstellungen aktualisieren
            project.keyword = request.POST.get('keyword', project.keyword)
            project.description = request.POST.get('description', '')
            project.script_type = request.POST.get('script_type', project.script_type)
            project.tone = request.POST.get('tone', project.tone)
            project.target_audience = request.POST.get('target_audience', project.target_audience)
            project.platform = request.POST.get('platform', project.platform)
            project.duration = float(request.POST.get('duration', project.duration))
            project.ai_model = request.POST.get('ai_model', project.ai_model)
            project.title = project.keyword[:200]
            project.save()
            messages.success(request, 'Einstellungen aktualisiert!')

        return redirect('vskript:detail', project_id=project.id)

    # Generation Logs laden
    generation_logs = project.generation_logs.all()[:5]

    context = {
        'project': project,
        'generation_logs': generation_logs,
        'script_types': SCRIPT_TYPE_CHOICES,
        'tones': TONE_CHOICES,
        'target_audiences': TARGET_AUDIENCE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'durations': DURATION_CHOICES,
        'ai_models': AI_MODEL_CHOICES,
    }

    return render(request, 'vskript/detail.html', context)


@login_required
@require_POST
def project_delete(request, project_id):
    """Projekt löschen"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)
    project.delete()
    messages.success(request, 'Projekt gelöscht!')
    return redirect('vskript:dashboard')


@login_required
@require_POST
def api_generate(request):
    """API: Skript generieren (für AJAX)"""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        keyword = data.get('keyword', '').strip()
        description = data.get('description', '').strip()
        script_type = data.get('script_type', 'interesting_facts')
        tone = data.get('tone', 'casual')
        target_audience = data.get('target_audience', 'general')
        platform = data.get('platform', 'youtube')
        duration = float(data.get('duration', 1.0))
        ai_model = data.get('ai_model', 'gpt-5')
        project_id = data.get('project_id')

        if not keyword:
            return JsonResponse({'success': False, 'error': 'Keyword ist erforderlich'}, status=400)

        # Settings laden (falls vorhanden)
        settings = None
        try:
            from blogprep.models import BlogPrepSettings
            settings = BlogPrepSettings.objects.filter(user=request.user).first()
        except Exception:
            pass

        # Service initialisieren
        service = VSkriptService(request.user, settings)

        # Skript generieren
        result = service.generate_script(
            keyword=keyword,
            description=description,
            script_type=script_type,
            tone=tone,
            target_audience=target_audience,
            platform=platform,
            duration_minutes=duration,
            ai_model=ai_model
        )

        if result['success']:
            # Falls project_id angegeben, Projekt aktualisieren
            if project_id:
                try:
                    project = VSkriptProject.objects.get(id=project_id, user=request.user)
                    project.script = result['script']
                    project.word_count = result['word_count']
                    project.estimated_duration = result['estimated_duration_minutes']
                    project.save()

                    # Log erstellen
                    VSkriptGenerationLog.objects.create(
                        project=project,
                        provider=result.get('provider', 'unknown'),
                        model=result.get('model', 'unknown'),
                        prompt=f"Keyword: {keyword}, Type: {script_type}, Tone: {tone}",
                        response=result['script'][:1000],
                        tokens_input=result.get('tokens_input', 0),
                        tokens_output=result.get('tokens_output', 0),
                        duration=result.get('duration', 0)
                    )
                except VSkriptProject.DoesNotExist:
                    pass

            # Model-Label für Anzeige ermitteln
            model_label = dict(AI_MODEL_CHOICES).get(ai_model, ai_model)

            return JsonResponse({
                'success': True,
                'script': result['script'],
                'word_count': result['word_count'],
                'estimated_duration': result['estimated_duration_minutes'],
                'ai_model': ai_model,
                'ai_model_label': model_label
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_regenerate(request, project_id):
    """API: Skript neu generieren"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)

    # Settings laden
    settings = None
    try:
        from blogprep.models import BlogPrepSettings
        settings = BlogPrepSettings.objects.filter(user=request.user).first()
    except Exception:
        pass

    # Service initialisieren
    service = VSkriptService(request.user, settings)

    # Skript generieren
    result = service.generate_script(
        keyword=project.keyword,
        description=project.description,
        script_type=project.script_type,
        tone=project.tone,
        target_audience=project.target_audience,
        platform=project.platform,
        duration_minutes=project.duration,
        ai_model=project.ai_model
    )

    if result['success']:
        project.script = result['script']
        project.word_count = result['word_count']
        project.estimated_duration = result['estimated_duration_minutes']
        project.save()

        # Log erstellen
        VSkriptGenerationLog.objects.create(
            project=project,
            provider=result.get('provider', 'unknown'),
            model=result.get('model', 'unknown'),
            prompt=f"Regenerate - Keyword: {project.keyword}",
            response=result['script'][:1000],
            tokens_input=result.get('tokens_input', 0),
            tokens_output=result.get('tokens_output', 0),
            duration=result.get('duration', 0)
        )

        # Model-Label für Anzeige ermitteln
        model_label = dict(AI_MODEL_CHOICES).get(project.ai_model, project.ai_model)

        return JsonResponse({
            'success': True,
            'script': result['script'],
            'word_count': result['word_count'],
            'estimated_duration': result['estimated_duration_minutes'],
            'ai_model': project.ai_model,
            'ai_model_label': model_label
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Unbekannter Fehler')
        }, status=500)

"""
VSkript Views

Dashboard, Create, Detail und API-Endpunkte für Videoskript-Generierung.
"""

import json
import zipfile
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator

from .models import (
    VSkriptProject,
    VSkriptGenerationLog,
    VSkriptImage,
    SCRIPT_TYPE_CHOICES,
    TONE_CHOICES,
    TARGET_AUDIENCE_CHOICES,
    PLATFORM_CHOICES,
    DURATION_CHOICES,
    AI_MODEL_CHOICES,
    IMAGE_INTERVAL_CHOICES,
    IMAGE_STYLE_CHOICES,
    IMAGE_MODEL_CHOICES,
    IMAGE_FORMAT_CHOICES,
)
from .services import VSkriptService, VSkriptImageService


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
        ai_model = request.POST.get('ai_model', 'gpt-4o')

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

        elif action == 'update_image_settings':
            # Bild-Einstellungen aktualisieren
            project.image_interval = int(request.POST.get('image_interval', project.image_interval))
            project.image_style = request.POST.get('image_style', project.image_style)
            project.image_model = request.POST.get('image_model', project.image_model)
            project.image_format = request.POST.get('image_format', project.image_format)
            project.save()
            messages.success(request, 'Bild-Einstellungen aktualisiert!')

        return redirect('vskript:detail', project_id=project.id)

    # Generation Logs laden
    generation_logs = project.generation_logs.all()[:5]

    # Bilder laden
    images = project.images.all().order_by('order')

    context = {
        'project': project,
        'generation_logs': generation_logs,
        'images': images,
        'script_types': SCRIPT_TYPE_CHOICES,
        'tones': TONE_CHOICES,
        'target_audiences': TARGET_AUDIENCE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'durations': DURATION_CHOICES,
        'ai_models': AI_MODEL_CHOICES,
        'image_intervals': IMAGE_INTERVAL_CHOICES,
        'image_styles': IMAGE_STYLE_CHOICES,
        'image_models': IMAGE_MODEL_CHOICES,
        'image_formats': IMAGE_FORMAT_CHOICES,
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
        ai_model = data.get('ai_model', 'gpt-4o')
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


# === IMAGE API ENDPOINTS ===

@login_required
@require_POST
def api_generate_images(request, project_id):
    """API: Alle Bilder für ein Projekt generieren"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)

    if not project.script:
        return JsonResponse({
            'success': False,
            'error': 'Bitte zuerst ein Skript generieren'
        }, status=400)

    try:
        # Image Service initialisieren
        service = VSkriptImageService(request.user)

        # Prompts aus Skript generieren
        prompts = service.generate_prompts_from_script(
            script=project.script,
            interval_seconds=project.image_interval,
            duration_minutes=project.estimated_duration,
            keyword=project.keyword
        )

        # Alte Bilder löschen
        project.images.all().delete()

        # Neue Bild-Objekte erstellen
        created_images = []
        for prompt_data in prompts:
            image = VSkriptImage.objects.create(
                project=project,
                position_seconds=prompt_data['position_seconds'],
                order=prompt_data['order'],
                prompt=prompt_data['prompt'],
                model_used=project.image_model,
                style_used=project.image_style,
                format_used=project.image_format,
                status='pending'
            )
            created_images.append({
                'id': str(image.id),
                'order': image.order,
                'position_seconds': image.position_seconds,
                'prompt': image.prompt,
                'status': image.status
            })

        return JsonResponse({
            'success': True,
            'images': created_images,
            'total': len(created_images),
            'message': f'{len(created_images)} Bild-Prompts erstellt. Generierung starten.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_single_image(request, image_id):
    """API: Einzelnes Bild generieren"""
    image = get_object_or_404(VSkriptImage, id=image_id, project__user=request.user)

    try:
        # Status aktualisieren
        image.status = 'generating'
        image.save()

        # Image Service initialisieren
        service = VSkriptImageService(request.user)

        # Bild generieren
        result = service.generate_image(
            prompt=image.prompt,
            style=image.style_used,
            model=image.model_used,
            format=image.format_used,
            context=image.project.keyword
        )

        if result['success']:
            image.prompt_enhanced = result.get('enhanced_prompt', '')
            image.status = 'completed'
            image.error_message = ''

            # Bild speichern
            if 'image_url' in result:
                service.save_image_to_model(image, image_url=result['image_url'])
            elif 'image_data' in result:
                service.save_image_to_model(image, image_data=result['image_data'])

            return JsonResponse({
                'success': True,
                'image_id': str(image.id),
                'image_url': image.image_file.url if image.image_file else image.image_url,
                'status': 'completed'
            })
        else:
            image.status = 'failed'
            image.error_message = result.get('error', 'Unbekannter Fehler')
            image.save()

            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        image.status = 'failed'
        image.error_message = str(e)
        image.save()

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_regenerate_image(request, image_id):
    """API: Einzelnes Bild neu generieren"""
    image = get_object_or_404(VSkriptImage, id=image_id, project__user=request.user)

    # Prompt aus Request übernehmen falls vorhanden
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else {}
        new_prompt = data.get('prompt', '').strip()
        if new_prompt:
            image.prompt = new_prompt
            image.save()
    except:
        pass

    # Bild neu generieren (verwendet api_generate_single_image Logik)
    return api_generate_single_image(request, image_id)


@login_required
def api_download_image(request, image_id):
    """API: Einzelnes Bild herunterladen"""
    image = get_object_or_404(VSkriptImage, id=image_id, project__user=request.user)

    if not image.image_file:
        return JsonResponse({'error': 'Bild nicht gefunden'}, status=404)

    response = HttpResponse(image.image_file.read(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="vskript_bild_{image.order + 1}.png"'
    return response


@login_required
def api_download_all_images(request, project_id):
    """API: Alle Bilder als ZIP herunterladen"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)
    images = project.images.filter(status='completed').order_by('order')

    if not images.exists():
        return JsonResponse({'error': 'Keine fertigen Bilder vorhanden'}, status=404)

    # ZIP erstellen
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for image in images:
            if image.image_file:
                filename = f"bild_{image.order + 1:02d}_{image.position_seconds:.1f}s.png"
                zip_file.writestr(filename, image.image_file.read())

    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="vskript_{project.keyword[:20]}_bilder.zip"'
    return response


@login_required
@require_POST
def api_delete_image(request, image_id):
    """API: Einzelnes Bild löschen"""
    image = get_object_or_404(VSkriptImage, id=image_id, project__user=request.user)
    image.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_delete_all_images(request, project_id):
    """API: Alle Bilder eines Projekts löschen"""
    project = get_object_or_404(VSkriptProject, id=project_id, user=request.user)
    project.images.all().delete()
    return JsonResponse({'success': True})

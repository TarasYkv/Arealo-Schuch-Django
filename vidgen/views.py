from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import VideoProject, BatchJob, TEMPLATE_CHOICES, PLATFORM_CHOICES, VOICE_CHOICES
from .tasks import generate_video, process_batch


@login_required
def vidgen_home(request):
    """Startseite von VidGen"""
    recent_projects = VideoProject.objects.filter(user=request.user)[:10]
    recent_batches = BatchJob.objects.filter(user=request.user)[:5]
    
    context = {
        'recent_projects': recent_projects,
        'recent_batches': recent_batches,
        'templates': TEMPLATE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'voices': VOICE_CHOICES,
        'title_positions': [('top', 'Oben'), ('center', 'Mitte'), ('bottom', 'Unten')],
    }
    return render(request, 'vidgen/home.html', context)


@login_required
def create_single(request):
    """Einzelnes Video erstellen"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        template = request.POST.get('template', 'job_intro')
        platform = request.POST.get('platform', 'tiktok')
        voice = request.POST.get('voice', 'echo')
        title_position = request.POST.get('title_position', 'top')
        target_duration = int(request.POST.get('target_duration', 45))
        resolution = request.POST.get('resolution', '1080p')
        render_backend = request.POST.get('render_backend', 'local')
        custom_script = request.POST.get('custom_script', '').strip()
        watermark = request.POST.get('watermark') == 'on'
        overlay_start = int(request.POST.get('overlay_start', 5))
        overlay_position = request.POST.get('overlay_position', 'center')
        overlay_width = int(request.POST.get('overlay_width', 60))
        overlay_duration = int(request.POST.get('overlay_duration', 0))
        intro_style = request.POST.get('intro_style', 'none')
        transition_style = request.POST.get('transition_style', 'cut')
        lower_third_text = request.POST.get('lower_third_text', '')
        lower_third_start = int(request.POST.get('lower_third_start', 0))
        show_progress_bar = request.POST.get('show_progress_bar') == 'on'
        progress_bar_color = request.POST.get('progress_bar_color', '#FFD700')
        emoji_animations = request.POST.get('emoji_animations') == 'on'
        # Erweiterte Effekte
        ken_burns_effect = request.POST.get('ken_burns_effect') == 'on'
        color_grading = request.POST.get('color_grading', 'none')
        quote_text = request.POST.get('quote_text', '')
        quote_author = request.POST.get('quote_author', '')
        quote_time = int(request.POST.get("quote_time", 0))
        quote_duration = int(request.POST.get("quote_duration", 5))
        fact_box_text = request.POST.get('fact_box_text', '')
        fact_box_time = int(request.POST.get("fact_box_time", 0))
        fact_box_duration = int(request.POST.get("fact_box_duration", 5))
        background_music = request.POST.get('background_music', 'none')
        selected_music_track_id = request.POST.get('selected_music_track_id', '')
        music_volume = int(request.POST.get('music_volume', 20))
        custom_music_prompt = request.POST.get('custom_music_prompt', '')
        music_duration = int(request.POST.get('music_duration', 0))
        sound_effects = request.POST.get('sound_effects') == 'on'
        audio_ducking = request.POST.get('audio_ducking') == 'on'
        is_discussion = request.POST.get('is_discussion') == 'on' or template == 'discussion'
        speaker1_name = request.POST.get('speaker1_name', 'Pro')
        speaker1_voice = request.POST.get('speaker1_voice', 'alloy')
        speaker2_name = request.POST.get('speaker2_name', 'Contra')
        speaker2_voice = request.POST.get('speaker2_voice', 'echo')
        
        if not title:
            messages.error(request, 'Bitte gib einen Titel/Thema ein.')
            return redirect('vidgen:create_single')
        
        # Prüfen ob API Keys vorhanden
        if not request.user.openai_api_key:
            messages.error(request, 'Bitte hinterlege zuerst deinen OpenAI API-Key in den API-Einstellungen.')
            return redirect('neue_api_einstellungen')
        
        if not getattr(request.user, 'pexels_api_key', None):
            messages.error(request, 'Bitte hinterlege zuerst deinen Pexels API-Key in den API-Einstellungen.')
            return redirect('neue_api_einstellungen')
        
        # Projekt erstellen
        project = VideoProject.objects.create(
            user=request.user,
            title=title,
            template=template,
            platform=platform,
            voice=voice,
            title_position=title_position,
            target_duration=target_duration,
            resolution=resolution,
            render_backend=render_backend,
            custom_script=custom_script,
            watermark=watermark,
            overlay_start=overlay_start,
            overlay_position=overlay_position,
            overlay_width=overlay_width,
            overlay_duration=overlay_duration,
            intro_style=intro_style,
            transition_style=transition_style,
            lower_third_text=lower_third_text,
            lower_third_start=lower_third_start,
            show_progress_bar=show_progress_bar,
            progress_bar_color=progress_bar_color,
            emoji_animations=emoji_animations,
            ken_burns_effect=ken_burns_effect,
            color_grading=color_grading,
            quote_text=quote_text,
            quote_author=quote_author,
            quote_time=quote_time,
            quote_duration=quote_duration,
            fact_box_text=fact_box_text,
            fact_box_time=fact_box_time,
            fact_box_duration=fact_box_duration,
            background_music=background_music,
            music_volume=music_volume,
            custom_music_prompt=custom_music_prompt,
            music_duration=music_duration,
            sound_effects=sound_effects,
            audio_ducking=audio_ducking,
            is_discussion=is_discussion,
            speaker1_name=speaker1_name,
            speaker1_voice=speaker1_voice,
            speaker2_name=speaker2_name,
            speaker2_voice=speaker2_voice,
        )
        
        # Musik-Track zuweisen falls ausgewählt
        if selected_music_track_id:
            try:
                from .models import MusicTrack
                track = MusicTrack.objects.get(id=selected_music_track_id)
                project.selected_music_track = track
                project.save(update_fields=["selected_music_track"])
            except:
                pass

        # Overlay speichern falls vorhanden
        if 'overlay' in request.FILES:
            project.overlay_file = request.FILES['overlay']
            project.save()
        
        # Celery Task starten
        generate_video.delay(str(project.id))
        
        messages.success(request, f'Video "{title}" wird erstellt! Du wirst benachrichtigt wenn es fertig ist.')
        return redirect('vidgen:project_detail', project_id=project.id)
    
    context = {
        'templates': TEMPLATE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'voices': VOICE_CHOICES,
        'title_positions': [('top', 'Oben'), ('center', 'Mitte'), ('bottom', 'Unten')],
    }
    return render(request, 'vidgen/create_single.html', context)


@login_required
def create_batch(request):
    """Batch-Job erstellen"""
    if request.method == 'POST':
        keywords = request.POST.get('keywords', '').strip()
        template = request.POST.get('template', 'job_intro')
        platform = request.POST.get('platform', 'tiktok')
        voice = request.POST.get('voice', 'echo')
        title_position = request.POST.get('title_position', 'top')
        target_duration = int(request.POST.get('target_duration', 45))
        resolution = request.POST.get('resolution', '1080p')
        render_backend = request.POST.get('render_backend', 'local')
        custom_script = request.POST.get('custom_script', '').strip()
        watermark = request.POST.get('watermark') == 'on'
        
        if not keywords:
            messages.error(request, 'Bitte gib mindestens ein Keyword ein.')
            return redirect('vidgen:create_batch')
        
        # Prüfen ob API Keys vorhanden
        if not request.user.openai_api_key:
            messages.error(request, 'Bitte hinterlege zuerst deinen OpenAI API-Key in den API-Einstellungen.')
            return redirect('neue_api_einstellungen')
        
        if not getattr(request.user, 'pexels_api_key', None):
            messages.error(request, 'Bitte hinterlege zuerst deinen Pexels API-Key in den API-Einstellungen.')
            return redirect('neue_api_einstellungen')
        
        # Batch erstellen
        batch = BatchJob.objects.create(
            user=request.user,
            keywords=keywords,
            template=template,
            platform=platform,
            voice=voice,
            title_position=title_position,
            target_duration=target_duration,
            resolution=resolution,
            render_backend=render_backend,
            custom_script=custom_script,
            watermark=watermark,
        )
        
        # Celery Task starten
        process_batch.delay(str(batch.id))
        
        keyword_count = len(batch.get_keywords_list())
        messages.success(request, f'Batch mit {keyword_count} Videos gestartet!')
        return redirect('vidgen:batch_detail', batch_id=batch.id)
    
    context = {
        'templates': TEMPLATE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'voices': VOICE_CHOICES,
        'title_positions': [('top', 'Oben'), ('center', 'Mitte'), ('bottom', 'Unten')],
    }
    return render(request, 'vidgen/create_batch.html', context)


@login_required
def project_detail(request, project_id):
    """Projekt-Details anzeigen"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    context = {
        'project': project,
    }
    return render(request, 'vidgen/project_detail.html', context)


@login_required
def batch_detail(request, batch_id):
    """Batch-Details anzeigen"""
    batch = get_object_or_404(BatchJob, id=batch_id, user=request.user)
    projects = batch.projects.all().order_by('-created_at')
    
    context = {
        'batch': batch,
        'projects': projects,
    }
    return render(request, 'vidgen/batch_detail.html', context)


@login_required
def project_list(request):
    """Liste aller Projekte"""
    projects = VideoProject.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'projects': projects,
    }
    return render(request, 'vidgen/project_list.html', context)


@login_required
def batch_list(request):
    """Liste aller Batches"""
    batches = BatchJob.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'batches': batches,
    }
    return render(request, 'vidgen/batch_list.html', context)


@login_required
def project_status_api(request, project_id):
    """API: Projekt-Status abrufen"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    data = {
        'id': str(project.id),
        'title': project.title,
        'status': project.status,
        'status_display': project.get_status_display(),
        'progress': project.progress,
        'error_message': project.error_message,
        'cost_total': float(project.cost_total),
        'video_url': project.video.video_file.url if project.video else None,
    }
    
    return JsonResponse(data)


@login_required
def batch_status_api(request, batch_id):
    """API: Batch-Status abrufen"""
    batch = get_object_or_404(BatchJob, id=batch_id, user=request.user)
    
    data = {
        'id': str(batch.id),
        'status': batch.status,
        'status_display': batch.get_status_display(),
        'total_count': batch.total_count,
        'completed_count': batch.completed_count,
        'failed_count': batch.failed_count,
        'cost_total': float(batch.cost_total),
        'projects': [
            {
                'id': str(p.id),
                'title': p.title,
                'status': p.status,
                'status_display': p.get_status_display(),
                'progress': p.progress,
            }
            for p in batch.projects.all()
        ]
    }
    
    return JsonResponse(data)


@login_required
def regenerate_project(request, project_id):
    """Fehlgeschlagenes Projekt erneut generieren"""
    from .models import VideoProject
    from .tasks import generate_video
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    if project.status != 'failed':
        messages.warning(request, 'Nur fehlgeschlagene Projekte können erneut generiert werden.')
        return redirect('vidgen:project_detail', project_id=project.id)
    
    # Status zurücksetzen
    project.status = 'pending'
    project.progress = 0
    project.error_message = ''
    project.save()
    
    # Task neu starten
    generate_video.delay(str(project.id))
    
    messages.success(request, f'Video "{project.title}" wird erneut generiert!')
    return redirect('vidgen:project_detail', project_id=project.id)


@login_required
def delete_project(request, project_id):
    """Projekt löschen"""
    from .models import VideoProject
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    title = project.title
    
    # Video löschen falls vorhanden
    if project.video:
        project.video.delete()
    
    # Projekt löschen
    project.delete()
    
    messages.success(request, f'Projekt "{title}" wurde gelöscht.')
    return redirect('vidgen:project_list')


from django.http import JsonResponse

@login_required
def imageforge_images_api(request):
    """API für ImageForge Bilder"""
    try:
        from imageforge.models import ImageGeneration
        
        images = ImageGeneration.objects.filter(
            user=request.user,
            generated_image__isnull=False
        ).order_by('-created_at')[:50]
        
        return JsonResponse({
            'images': [
                {
                    'id': str(img.id),
                    'url': img.generated_image.url if img.generated_image else None,
                    'thumbnail': img.generated_image.url if img.generated_image else None,
                    'created': img.created_at.isoformat() if hasattr(img, 'created_at') else None,
                }
                for img in images if img.generated_image
            ]
        })
    except Exception as e:
        return JsonResponse({'images': [], 'error': str(e)})


# === Social Media Publishing ===

from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def generate_social_text(request, project_id):
    """Generiert Titel, Beschreibung und Hashtags aus dem Skript"""
    from openai import OpenAI
    
    try:
        project = VideoProject.objects.get(id=project_id, user=request.user)
    except VideoProject.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Projekt nicht gefunden'})
    
    if not project.script:
        return JsonResponse({'success': False, 'error': 'Kein Skript vorhanden'})
    
    # User's OpenAI API Key verwenden
    api_key = request.user.openai_api_key
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Kein OpenAI API Key hinterlegt'})
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Basierend auf diesem Video-Skript, erstelle Social-Media-Texte:

Skript:
{project.script[:2000]}

Erstelle:
1. Einen packenden Titel (max 60 Zeichen)
2. Eine Beschreibung mit Call-to-Action (max 300 Zeichen)  
3. 8-10 relevante Hashtags

Antwort als JSON:
{{"title": "...", "description": "...", "hashtags": "#tag1 #tag2 ..."}}"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'}
        )
        
        result = json.loads(response.choices[0].message.content)
        return JsonResponse({
            'success': True,
            'title': result.get('title', ''),
            'description': result.get('description', ''),
            'hashtags': result.get('hashtags', '')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST  
def publish_video(request, project_id):
    """Veröffentlicht das Video auf Social Media"""
    try:
        project = VideoProject.objects.get(id=project_id, user=request.user)
    except VideoProject.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Projekt nicht gefunden'})
    
    if not project.video:
        return JsonResponse({'success': False, 'error': 'Kein Video vorhanden'})
    
    data = json.loads(request.body)
    platforms = data.get('platforms', [])
    title = data.get('title', '')
    description = data.get('description', '')
    hashtags = data.get('hashtags', '')
    
    # Redirect to videos app social posting
    from videos.views import post_to_social_media
    
    # Create a mock request with the video data
    result = post_to_social_media(
        request,
        video_id=project.video.id,
        platforms=platforms,
        title=title,
        description=description + '\n\n' + hashtags
    )
    
    return result


@login_required
@require_POST
def generate_quotes_api(request):
    """Generiert 10 Zitate zu einem Thema"""
    from openai import OpenAI
    
    data = json.loads(request.body)
    theme = data.get('theme', 'allgemein')
    
    # User's OpenAI API Key verwenden
    api_key = request.user.openai_api_key
    if not api_key:
        return JsonResponse({'quotes': [], 'error': 'Kein OpenAI API Key hinterlegt'})
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Generiere 10 inspirierende, passende Zitate zum Thema: {theme}

Die Zitate sollten kurz, prägnant und für Social-Media-Videos geeignet sein (max 100 Zeichen).
Mix aus bekannten Persönlichkeiten und passenden Autoren.

Antwort als JSON:
{{"quotes": [{{"text": "Zitat hier", "author": "Autor Name"}}, ...]}}"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'}
        )
        result = json.loads(response.choices[0].message.content)
        return JsonResponse({'quotes': result.get('quotes', [])})
    except Exception as e:
        return JsonResponse({'quotes': [], 'error': str(e)})


@login_required
@require_POST
def generate_facts_api(request):
    """Generiert 10 Fakten zu einem Thema"""
    from openai import OpenAI
    
    data = json.loads(request.body)
    theme = data.get('theme', 'allgemein')
    
    # User's OpenAI API Key verwenden
    api_key = request.user.openai_api_key
    if not api_key:
        return JsonResponse({'facts': [], 'error': 'Kein OpenAI API Key hinterlegt'})
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Generiere 10 interessante, überraschende Fakten zum Thema: {theme}

Die Fakten sollten:
- Kurz und prägnant sein (max 80 Zeichen)
- Mit einer Zahl/Prozent beginnen wenn möglich (z.B. "85% der Menschen...")
- Für Social-Media-Videos geeignet sein
- Aufmerksamkeit erregen

Antwort als JSON:
{{"facts": ["Fakt 1", "Fakt 2", ...]}}"""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'}
        )
        result = json.loads(response.choices[0].message.content)
        return JsonResponse({'facts': result.get('facts', [])})
    except Exception as e:
        return JsonResponse({'facts': [], 'error': str(e)})


# ============================================
# MANUELLER WORKFLOW - Schritt für Schritt
# ============================================

@login_required
def project_edit(request, project_id):
    """Projekt bearbeiten - manueller Workflow"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    context = {
        'project': project,
        'templates': TEMPLATE_CHOICES,
        'platforms': PLATFORM_CHOICES,
        'voices': VOICE_CHOICES,
    }
    return render(request, 'vidgen/project_edit.html', context)


@login_required
@require_POST
def step_generate_script(request, project_id):
    """Schritt 1: Skript generieren/neu generieren"""
    from .tasks import generate_script_only
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    # Optional: Neues custom_script aus POST
    custom_script = request.POST.get('custom_script', '').strip()
    if custom_script:
        project.custom_script = custom_script
        project.script = custom_script
        project.save()
        return JsonResponse({'success': True, 'script': custom_script, 'message': 'Eigener Text übernommen'})
    
    # Skript mit KI generieren
    try:
        script = generate_script_only(project)
        project.script = script
        project.status = 'script'
        project.progress = 10
        project.save()
        return JsonResponse({'success': True, 'script': script, 'message': 'Skript generiert'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def step_update_script(request, project_id):
    """Schritt 1b: Skript manuell aktualisieren"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    data = json.loads(request.body)
    script = data.get('script', '').strip()
    
    if not script:
        return JsonResponse({'success': False, 'error': 'Kein Skript angegeben'})
    
    project.script = script
    project.save()
    return JsonResponse({'success': True, 'message': 'Skript aktualisiert'})


@login_required
@require_POST
def step_generate_audio(request, project_id):
    """Schritt 2: Audio generieren"""
    from .tasks import generate_audio_only
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    if not project.script:
        return JsonResponse({'success': False, 'error': 'Kein Skript vorhanden. Bitte zuerst Skript generieren.'})
    
    try:
        audio_path, duration = generate_audio_only(project)
        project.status = 'audio'
        project.progress = 30
        project.save()
        return JsonResponse({
            'success': True, 
            'message': f'Audio generiert ({duration:.1f}s)',
            'duration': duration,
            'audio_url': project.audio_file.url if project.audio_file else ''
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def step_fetch_clips(request, project_id):
    """Schritt 3: Video-Clips suchen"""
    from .tasks import fetch_clips_only
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    # Optional: Custom Keywords aus POST
    data = json.loads(request.body) if request.body else {}
    custom_keywords = data.get('keywords', [])
    
    try:
        clips = fetch_clips_only(project, custom_keywords=custom_keywords)
        project.status = 'clips'
        project.progress = 50
        project.save()
        
        clip_info = [{'keyword': c.search_query, 'pexels_id': c.pexels_id} for c in clips]
        return JsonResponse({
            'success': True,
            'message': f'{len(clips)} Clips gefunden',
            'clips': clip_info
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def step_search_new_clip(request, project_id):
    """Einzelnen Clip neu suchen"""
    from .tasks import search_single_clip
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    data = json.loads(request.body)
    clip_index = data.get('clip_index', 0)
    new_keyword = data.get('keyword', '')
    
    if not new_keyword:
        return JsonResponse({'success': False, 'error': 'Kein Suchbegriff angegeben'})
    
    try:
        clip = search_single_clip(project, clip_index, new_keyword)
        return JsonResponse({
            'success': True,
            'message': f'Neuer Clip gefunden: {clip.pexels_id}',
            'clip': {
                'keyword': clip.search_query,
                'pexels_id': clip.pexels_id,
                'duration': clip.duration
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def step_render_video(request, project_id):
    """Schritt 4: Video rendern"""
    from .tasks import render_video_only
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    if project.clips.count() == 0:
        return JsonResponse({'success': False, 'error': 'Keine Clips vorhanden. Bitte zuerst Clips suchen.'})
    
    # Render als Celery Task starten
    render_video_only.delay(str(project.id))
    
    project.status = 'rendering'
    project.progress = 70
    project.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Rendering gestartet...'
    })


@login_required
def get_project_clips(request, project_id):
    """Gibt alle Clips eines Projekts zurück"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    clips = []
    for clip in project.clips.all().order_by('order'):
        clips.append({
            'id': str(clip.id),
            'order': clip.order,
            'keyword': clip.search_query,
            'pexels_id': clip.pexels_id,
            'duration': clip.duration,
            'preview_url': f'https://player.vimeo.com/external/{clip.pexels_id}' if clip.pexels_id else None
        })
    
    return JsonResponse({'clips': clips})


@login_required
@require_POST
def restart_from_step(request, project_id):
    """Projekt ab einem bestimmten Schritt neu starten"""
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    data = json.loads(request.body)
    step = data.get('step', 'script')
    
    if step == 'script':
        project.script = ''
        project.status = 'pending'
        project.progress = 0
        project.clips.all().delete()
    elif step == 'audio':
        project.status = 'script'
        project.progress = 10
        project.clips.all().delete()
    elif step == 'clips':
        project.status = 'audio'
        project.progress = 30
        project.clips.all().delete()
    elif step == 'render':
        project.status = 'clips'
        project.progress = 50
    
    project.error_message = ''
    project.save()
    
    return JsonResponse({'success': True, 'message': f'Projekt zurückgesetzt auf Schritt: {step}'})


@login_required
@require_POST
def step_generate_music(request, project_id):
    """Schritt 3: Hintergrundmusik generieren (async via Celery)"""
    from .tasks import generate_music_task
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    
    data = json.loads(request.body) if request.body else {}
    music_style = data.get('music_style', project.background_music)
    custom_prompt = data.get('custom_prompt', project.custom_music_prompt)
    
    # Projekt aktualisieren
    if music_style:
        project.background_music = music_style
    if custom_prompt:
        project.custom_music_prompt = custom_prompt
    project.save()
    
    # Celery Task starten (async!)
    task = generate_music_task.delay(str(project.id), music_style, custom_prompt)
    
    return JsonResponse({
        'success': True,
        'message': 'Musik-Generierung gestartet...',
        'task_id': task.id
    })


@login_required
def get_task_status(request, project_id, task_id):
    """Celery Task Status abfragen"""
    from celery.result import AsyncResult
    
    try:
        result = AsyncResult(task_id)
        
        if result.state == 'SUCCESS':
            return JsonResponse({
                'state': 'SUCCESS',
                'result': result.result
            })
        elif result.state == 'FAILURE':
            return JsonResponse({
                'state': 'FAILURE',
                'error': str(result.result)
            })
        else:
            return JsonResponse({
                'status': result.state  # PENDING, STARTED, RETRY, etc.
            })
    except Exception as e:
        return JsonResponse({
            'state': 'FAILURE',
            'error': str(e)
        })

# Neue Views für Musik-Bibliothek und Pixabay-Suche
# Einfügen in vidgen/views.py

@login_required
def musik_bibliothek(request):
    """Alle verfügbaren Musik-Tracks"""
    from .models import MusicTrack
    
    tracks = MusicTrack.objects.all().order_by("mood", "prompt")[:500]
    
    return JsonResponse({
        'tracks': [{
            'id': str(t.id),
            'title': t.prompt[:50] if t.prompt else f'{t.mood} Track',
            'mood': t.mood or 'custom',
            'duration': t.duration,
            'audio_url': t.audio_file.url if t.audio_file else '',
            'usage_count': t.usage_count
        } for t in tracks]
    })


@login_required
def pixabay_musik_suche(request):
    """Musik auf Pixabay suchen"""
    from .pixabay_music import search_pixabay_music
    
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'error': 'Suchbegriff fehlt'}, status=400)
    
    user = request.user
    api_key = getattr(user, 'pixabay_api_key', None)
    if not api_key:
        return JsonResponse({'error': 'Kein Pixabay API Key konfiguriert. Bitte in Profileinstellungen hinzufügen.'}, status=400)
    
    import requests
    url = "https://pixabay.com/api/music/"
    params = {
        'key': api_key,
        'q': query,
        'per_page': 12,
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        tracks = [{
            'id': str(hit.get('id')),
            'title': hit.get('title', 'Unbekannt'),
            'user': hit.get('user', 'Unbekannt'),
            'duration': hit.get('duration', 0),
            'preview_url': hit.get('audio', ''),
            'download_url': hit.get('audio', ''),
            'tags': hit.get('tags', '')
        } for hit in data.get('hits', [])]
        
        return JsonResponse({'tracks': tracks})
    except Exception as e:
        return JsonResponse({'error': f'Pixabay-Fehler: {str(e)}'}, status=500)


@login_required
@require_POST
def musik_waehlen(request, project_id):
    """Musik-Track für Projekt auswählen"""
    from .models import VideoProject, MusicTrack
    import json
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    data = json.loads(request.body)
    track_id = data.get('track_id')
    
    if track_id:
        track = get_object_or_404(MusicTrack, id=track_id)
        project.selected_music_track = track
        project.background_music = track.mood or 'custom'
        track.usage_count += 1
        track.save()
    else:
        project.selected_music_track = None
        project.background_music = 'none'
    
    project.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def musik_laden(request, project_id):
    """Pixabay-Track herunterladen und zur Bibliothek hinzufügen"""
    from .models import VideoProject, MusicTrack
    from .pixabay_music import download_pixabay_track
    from django.core.files import File
    import json
    import requests
    import os
    import tempfile
    
    project = get_object_or_404(VideoProject, id=project_id, user=request.user)
    data = json.loads(request.body)
    pixabay_id = data.get('pixabay_id')
    mood = data.get('mood', 'custom')
    
    user = request.user
    api_key = getattr(user, 'pixabay_api_key', None)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Kein Pixabay API Key'})
    
    # Track-Details holen
    url = f"https://pixabay.com/api/music/?key={api_key}&id={pixabay_id}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('hits'):
            return JsonResponse({'success': False, 'error': 'Track nicht gefunden'})
        
        hit = data['hits'][0]
        audio_url = hit.get('audio')
        title = hit.get('title', f'Pixabay {pixabay_id}')
        duration = hit.get('duration', 30)
        
        # Audio herunterladen
        audio_response = requests.get(audio_url, timeout=60)
        audio_response.raise_for_status()
        
        # In Bibliothek speichern
        track = MusicTrack.objects.create(
            prompt=f"Pixabay: {title}",
            mood=mood,
            duration=duration,
            usage_count=1,
            tags=f"pixabay,{mood},{hit.get('tags', '')[:100]}"
        )
        
        # Datei speichern
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, f"pixabay_{pixabay_id}.mp3")
        with open(temp_path, 'wb') as f:
            f.write(audio_response.content)
        
        with open(temp_path, 'rb') as f:
            track.audio_file.save(f"pixabay_{mood}_{track.id}.mp3", File(f))
        track.save()
        
        # Cleanup
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        # Projekt updaten
        project.selected_music_track = track
        project.background_music = mood
        project.save()
        
        return JsonResponse({
            'success': True,
            'track_id': str(track.id),
            'title': title,
            'audio_url': track.audio_file.url
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def musik_hochladen(request):
    """Musik-Datei hochladen und zur Bibliothek hinzufügen"""
    from .models import MusicTrack
    from pydub import AudioSegment
    import tempfile
    import os
    
    audio_file = request.FILES.get('audio_file')
    mood = request.POST.get('mood', 'custom')
    
    if not audio_file:
        return JsonResponse({'success': False, 'error': 'Keine Datei hochgeladen'})
    
    # Dateiformat prüfen
    allowed_types = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/x-wav']
    if audio_file.content_type not in allowed_types:
        return JsonResponse({'success': False, 'error': f'Ungültiges Format: {audio_file.content_type}'})
    
    try:
        # Temporär speichern um Dauer zu berechnen
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, audio_file.name)
        with open(temp_path, 'wb') as f:
            for chunk in audio_file.chunks():
                f.write(chunk)
        
        # Dauer berechnen
        try:
            if audio_file.name.endswith('.mp3'):
                audio = AudioSegment.from_mp3(temp_path)
            elif audio_file.name.endswith('.wav'):
                audio = AudioSegment.from_wav(temp_path)
            else:
                audio = AudioSegment.from_file(temp_path)
            duration = int(len(audio) / 1000)
        except:
            duration = 60  # Fallback
        
        # Track erstellen
        title = os.path.splitext(audio_file.name)[0]
        track = MusicTrack.objects.create(
            prompt=f'Upload: {title}',
            mood=mood,
            duration=duration,
            usage_count=1,
            tags=f'upload,{mood}'
        )
        
        # Datei speichern
        from django.core.files import File
        with open(temp_path, 'rb') as f:
            ext = os.path.splitext(audio_file.name)[1] or '.mp3'
            track.audio_file.save(f'{mood}_{track.id}{ext}', File(f))
        track.save()
        
        # Cleanup
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        return JsonResponse({
            'success': True,
            'track_id': str(track.id),
            'title': title,
            'audio_url': track.audio_file.url
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

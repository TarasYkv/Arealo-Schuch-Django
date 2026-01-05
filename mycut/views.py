# mycut/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
import json
import logging
import os
import tempfile

from .models import EditProject, TimelineClip, Subtitle, TextOverlay, AIEditSuggestion, ExportJob
from videos.models import Video

logger = logging.getLogger(__name__)


# =============================================================================
# PROJEKT-VIEWS
# =============================================================================

@login_required
def project_list(request):
    """
    Liste aller MyCut-Projekte des Users.
    """
    projects = EditProject.objects.filter(user=request.user).select_related('source_video')

    context = {
        'title': 'MyCut - Meine Projekte',
        'projects': projects,
    }
    return render(request, 'mycut/project_list.html', context)


@login_required
def create_project(request, video_id):
    """
    Erstellt ein neues Projekt für ein Video und leitet zum Editor weiter.
    """
    video = get_object_or_404(Video, id=video_id, user=request.user)

    # Projekt erstellen
    project = EditProject.objects.create(
        user=request.user,
        source_video=video,
        name=f"Bearbeitung: {video.title}",
        estimated_duration=video.duration or 0,
    )

    # Initialen Video-Clip erstellen
    duration_ms = (video.duration or 0) * 1000
    TimelineClip.objects.create(
        project=project,
        clip_type='video',
        track_index=0,
        start_time=0,
        duration=duration_ms,
        source_start=0,
        source_end=duration_ms,
    )

    logger.info(f"Created MyCut project {project.id} for video {video.id}")

    return redirect('mycut:editor', project_id=project.id)


@login_required
def editor_view(request, project_id):
    """
    Haupt-Editor-Ansicht für ein Projekt.
    """
    project = get_object_or_404(
        EditProject.objects.select_related('source_video', 'user'),
        id=project_id,
        user=request.user
    )

    # Clips, Untertitel und Vorschläge laden
    clips = project.clips.all()
    subtitles = project.subtitles.all()
    text_overlays = project.text_overlays.all()
    ai_suggestions = project.ai_suggestions.filter(is_applied=False, is_rejected=False)

    context = {
        'title': f'MyCut - {project.name}',
        'project': project,
        'video': project.source_video,
        'clips': clips,
        'subtitles': subtitles,
        'text_overlays': text_overlays,
        'ai_suggestions': ai_suggestions,
        'has_transcription': bool(project.ai_transcription),
    }
    return render(request, 'mycut/editor.html', context)


@login_required
def delete_project(request, project_id):
    """
    Löscht ein Projekt.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    if request.method == 'POST':
        project_name = project.name
        project.delete()
        logger.info(f"Deleted MyCut project: {project_name}")
        return redirect('mycut:list')

    context = {
        'title': f'Projekt löschen: {project.name}',
        'project': project,
    }
    return render(request, 'mycut/project_confirm_delete.html', context)


# =============================================================================
# API - PROJEKT-OPERATIONEN
# =============================================================================

@login_required
@require_http_methods(["GET"])
def api_project_detail(request, project_id):
    """
    Gibt Projekt-Details als JSON zurück.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    data = {
        'id': project.id,
        'name': project.name,
        'status': project.status,
        'source_video': {
            'id': project.source_video.id,
            'title': project.source_video.title,
            'url': project.source_video.video_file.url if project.source_video.video_file else None,
            'duration': project.source_video.duration,
        },
        'clips': list(project.clips.values()),
        'subtitles': list(project.subtitles.values()),
        'text_overlays': list(project.text_overlays.values()),
        'ai_suggestions': list(project.ai_suggestions.filter(
            is_applied=False, is_rejected=False
        ).values()),
        'project_data': project.project_data,
        'waveform_data': project.waveform_data,
        'has_transcription': bool(project.ai_transcription),
        'export_quality': project.export_quality,
        'export_format': project.export_format,
    }

    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def api_save_project(request, project_id):
    """
    Speichert Projekt-Änderungen.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)

        # Projekt-Daten aktualisieren
        if 'name' in data:
            project.name = data['name']
        if 'project_data' in data:
            project.project_data = data['project_data']
        if 'export_quality' in data:
            project.export_quality = data['export_quality']
        if 'export_format' in data:
            project.export_format = data['export_format']

        project.save()

        # Clips aktualisieren wenn vorhanden
        if 'clips' in data:
            project.clips.all().delete()
            for clip_data in data['clips']:
                TimelineClip.objects.create(
                    project=project,
                    clip_type=clip_data.get('clip_type', 'video'),
                    track_index=clip_data.get('track_index', 0),
                    start_time=clip_data.get('start_time', 0),
                    duration=clip_data.get('duration', 0),
                    source_start=clip_data.get('source_start', 0),
                    source_end=clip_data.get('source_end', 0),
                    clip_data=clip_data.get('clip_data', {}),
                    is_muted=clip_data.get('is_muted', False),
                    volume=clip_data.get('volume', 1.0),
                    speed=clip_data.get('speed', 1.0),
                )

        return JsonResponse({'success': True, 'message': 'Projekt gespeichert'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        logger.error(f"Save project error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# API - AI-FUNKTIONEN
# =============================================================================

@login_required
@require_http_methods(["POST"])
def api_transcribe(request, project_id):
    """
    Startet AI-Transkription für das Projekt.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    try:
        from .services.ai_service import MyCutAIService
        from .services.ffmpeg_service import FFmpegService

        ai_service = MyCutAIService(request.user)

        if not ai_service.is_available():
            return JsonResponse({
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert. Bitte in den Einstellungen hinterlegen.'
            }, status=400)

        # Audio extrahieren
        video_path = project.source_video.video_file.path
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            audio_path = tmp.name

        FFmpegService.extract_audio(video_path, audio_path)

        # Transkribieren
        transcription = ai_service.transcribe_audio(audio_path)

        # Ergebnis speichern
        project.ai_transcription = transcription
        project.save(update_fields=['ai_transcription'])

        # Temp-Datei löschen
        os.unlink(audio_path)

        # Alte Untertitel löschen (falls Retry)
        project.subtitles.filter(is_auto_generated=True).delete()

        # Alle Wörter für Zuordnung zu Segmenten
        all_words = transcription.get('words', [])

        # Untertitel aus Transkription erstellen
        for segment in transcription.get('segments', []):
            seg_start = segment.get('start', 0)
            seg_end = segment.get('end', 0)

            # Wörter für dieses Segment finden
            segment_words = [
                w for w in all_words
                if w.get('start', 0) >= seg_start and w.get('end', 0) <= seg_end
            ]

            Subtitle.objects.create(
                project=project,
                text=segment.get('text', '').strip(),
                start_time=seg_start,
                end_time=seg_end,
                word_timestamps=segment_words,
                is_auto_generated=True,
                confidence=0.9,
                language=transcription.get('language', 'de'),
            )

        return JsonResponse({
            'success': True,
            'message': 'Transkription abgeschlossen',
            'segments': len(transcription.get('segments', [])),
            'words': len(transcription.get('words', [])),
        })

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_analyze(request, project_id):
    """
    Analysiert Transkription für Auto-Edit-Vorschläge.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    if not project.ai_transcription:
        return JsonResponse({
            'success': False,
            'error': 'Keine Transkription vorhanden. Bitte erst transkribieren.'
        }, status=400)

    try:
        from .services.ai_service import MyCutAIService

        ai_service = MyCutAIService(request.user)
        language = project.ai_transcription.get('language', 'de')

        # Filler-Wörter erkennen
        fillers = ai_service.detect_filler_words(project.ai_transcription, language)
        for f in fillers:
            AIEditSuggestion.objects.create(
                project=project,
                suggestion_type='filler_word',
                start_time=f['start_time'],
                end_time=f['end_time'],
                text=f['text'],
                confidence=f['confidence'],
            )

        # Stille erkennen
        silences = ai_service.detect_silence_from_transcription(project.ai_transcription)
        for s in silences:
            AIEditSuggestion.objects.create(
                project=project,
                suggestion_type='silence',
                start_time=s['start_time'],
                end_time=s['end_time'],
                text=s['text'],
                confidence=s['confidence'],
            )

        # Speed-Änderungen vorschlagen
        speed_changes = ai_service.analyze_speech_speed(project.ai_transcription)
        for sc in speed_changes:
            AIEditSuggestion.objects.create(
                project=project,
                suggestion_type='speed_up',
                start_time=sc['start_time'],
                end_time=sc['end_time'],
                text=sc['text'],
                confidence=sc['confidence'],
                suggested_value=sc.get('suggested_value'),
            )

        total = len(fillers) + len(silences) + len(speed_changes)

        return JsonResponse({
            'success': True,
            'message': f'{total} Vorschläge erstellt',
            'filler_words': len(fillers),
            'silences': len(silences),
            'speed_changes': len(speed_changes),
        })

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_apply_suggestion(request, project_id, suggestion_id):
    """
    Wendet einen AI-Vorschlag an.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)
    suggestion = get_object_or_404(AIEditSuggestion, id=suggestion_id, project=project)

    suggestion.is_applied = True
    suggestion.save(update_fields=['is_applied'])

    return JsonResponse({
        'success': True,
        'message': f'Vorschlag angewendet: {suggestion.get_suggestion_type_display()}'
    })


@login_required
@require_http_methods(["POST"])
def api_reject_suggestion(request, project_id, suggestion_id):
    """
    Lehnt einen AI-Vorschlag ab.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)
    suggestion = get_object_or_404(AIEditSuggestion, id=suggestion_id, project=project)

    suggestion.is_rejected = True
    suggestion.save(update_fields=['is_rejected'])

    return JsonResponse({'success': True, 'message': 'Vorschlag abgelehnt'})


# =============================================================================
# API - UNTERTITEL
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def api_subtitles(request, project_id):
    """
    CRUD für Untertitel.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    if request.method == 'GET':
        subtitles = list(project.subtitles.values())
        return JsonResponse({'success': True, 'subtitles': subtitles})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            subtitle = Subtitle.objects.create(
                project=project,
                text=data.get('text', ''),
                start_time=data.get('start_time', 0),
                end_time=data.get('end_time', 0),
                style=data.get('style', {}),
                is_auto_generated=False,
            )

            return JsonResponse({
                'success': True,
                'subtitle_id': subtitle.id,
                'message': 'Untertitel erstellt'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_export_subtitles(request, project_id):
    """
    Exportiert Untertitel als SRT oder VTT.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)
    format_type = request.GET.get('format', 'srt')

    subtitles = project.subtitles.order_by('start_time')

    if format_type == 'vtt':
        content = "WEBVTT\n\n"
        for i, sub in enumerate(subtitles, 1):
            start = _ms_to_vtt_time(sub.start_time)
            end = _ms_to_vtt_time(sub.end_time)
            content += f"{start} --> {end}\n{sub.text}\n\n"
        content_type = 'text/vtt'
        filename = f"{project.name}_subtitles.vtt"
    else:
        content = ""
        for i, sub in enumerate(subtitles, 1):
            start = _ms_to_srt_time(sub.start_time)
            end = _ms_to_srt_time(sub.end_time)
            content += f"{i}\n{start} --> {end}\n{sub.text}\n\n"
        content_type = 'text/plain'
        filename = f"{project.name}_subtitles.srt"

    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _ms_to_srt_time(ms):
    """Konvertiert Millisekunden zu SRT-Zeitformat."""
    hours = int(ms // 3600000)
    minutes = int((ms % 3600000) // 60000)
    seconds = int((ms % 60000) // 1000)
    millis = int(ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _ms_to_vtt_time(ms):
    """Konvertiert Millisekunden zu VTT-Zeitformat."""
    hours = int(ms // 3600000)
    minutes = int((ms % 3600000) // 60000)
    seconds = int((ms % 60000) // 1000)
    millis = int(ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


# =============================================================================
# API - WAVEFORM
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def api_get_waveform(request, project_id):
    """
    GET: Gibt Waveform-Daten zurück (generiert bei Bedarf).
    POST: Speichert Client-generierte Waveform-Daten.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    # POST: Client-generierte Waveform speichern
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            waveform = data.get('waveform', [])

            if waveform and isinstance(waveform, list):
                project.waveform_data = waveform
                project.save(update_fields=['waveform_data'])
                return JsonResponse({
                    'success': True,
                    'message': 'Waveform gespeichert'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Keine gültigen Waveform-Daten'
                }, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # GET: Waveform abrufen oder generieren
    if project.waveform_data:
        return JsonResponse({
            'success': True,
            'waveform': project.waveform_data
        })

    # Waveform generieren
    try:
        from .services.ffmpeg_service import FFmpegService

        video_path = project.source_video.video_file.path
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            audio_path = tmp.name

        FFmpegService.extract_audio(video_path, audio_path)
        waveform = FFmpegService.generate_waveform_data(audio_path)

        # Speichern
        project.waveform_data = waveform
        project.save(update_fields=['waveform_data'])

        os.unlink(audio_path)

        return JsonResponse({
            'success': True,
            'waveform': waveform
        })

    except Exception as e:
        logger.error(f"Waveform generation error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# API - EXPORT
# =============================================================================

@login_required
@require_http_methods(["POST"])
def api_start_export(request, project_id):
    """
    Startet den Video-Export.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body) if request.body else {}

        # Export-Job erstellen
        export_job = ExportJob.objects.create(
            project=project,
            export_settings={
                'quality': data.get('quality', project.export_quality),
                'format': data.get('format', project.export_format),
                'burn_subtitles': data.get('burn_subtitles', False),
            }
        )

        # TODO: Celery Task starten
        # from .tasks import export_video
        # task = export_video.delay(project.id, export_job.id)
        # export_job.celery_task_id = task.id
        # export_job.save()

        # Für jetzt: Direkt als "processing" markieren
        export_job.start_processing()

        return JsonResponse({
            'success': True,
            'job_id': export_job.id,
            'message': 'Export gestartet'
        })

    except Exception as e:
        logger.error(f"Export start error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_export_status(request, project_id):
    """
    Gibt den Export-Status zurück.
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    job = project.export_jobs.order_by('-created_at').first()

    if not job:
        return JsonResponse({'success': False, 'error': 'Kein Export-Job gefunden'}, status=404)

    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'status': job.status,
        'progress': job.progress,
        'error_message': job.error_message,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
    })


# =============================================================================
# API - TEXT-OVERLAYS
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def api_text_overlays(request, project_id):
    """
    GET: Liste aller Text-Overlays
    POST: Neues Text-Overlay erstellen
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)

    if request.method == 'GET':
        overlays = project.text_overlays.all().values()
        return JsonResponse({
            'success': True,
            'overlays': list(overlays)
        })

    # POST: Neues Overlay erstellen
    try:
        data = json.loads(request.body) if request.body else {}

        overlay = TextOverlay.objects.create(
            project=project,
            text=data.get('text', 'Text'),
            start_time=data.get('start_time', 0),
            end_time=data.get('end_time', 3000),
            position_x=data.get('position_x', 50),
            position_y=data.get('position_y', 50),
            style=data.get('style', {
                'font': 'Arial',
                'size': 48,
                'color': '#FFFFFF',
                'bold': True,
                'shadow': True,
            }),
            animation_in=data.get('animation_in', 'fade_in'),
            animation_out=data.get('animation_out', 'fade_out'),
            animation_duration=data.get('animation_duration', 500),
        )

        return JsonResponse({
            'success': True,
            'overlay': {
                'id': overlay.id,
                'text': overlay.text,
                'start_time': overlay.start_time,
                'end_time': overlay.end_time,
                'position_x': overlay.position_x,
                'position_y': overlay.position_y,
                'style': overlay.style,
                'animation_in': overlay.animation_in,
                'animation_out': overlay.animation_out,
            }
        })

    except Exception as e:
        logger.error(f"Create text overlay error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET", "PUT", "DELETE"])
def api_text_overlay_detail(request, project_id, overlay_id):
    """
    GET: Einzelnes Text-Overlay
    PUT: Text-Overlay aktualisieren
    DELETE: Text-Overlay löschen
    """
    project = get_object_or_404(EditProject, id=project_id, user=request.user)
    overlay = get_object_or_404(TextOverlay, id=overlay_id, project=project)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'overlay': {
                'id': overlay.id,
                'text': overlay.text,
                'start_time': overlay.start_time,
                'end_time': overlay.end_time,
                'position_x': overlay.position_x,
                'position_y': overlay.position_y,
                'style': overlay.style,
                'animation_in': overlay.animation_in,
                'animation_out': overlay.animation_out,
            }
        })

    if request.method == 'DELETE':
        overlay.delete()
        return JsonResponse({'success': True, 'message': 'Text-Overlay gelöscht'})

    # PUT: Update
    try:
        data = json.loads(request.body) if request.body else {}

        if 'text' in data:
            overlay.text = data['text']
        if 'start_time' in data:
            overlay.start_time = data['start_time']
        if 'end_time' in data:
            overlay.end_time = data['end_time']
        if 'position_x' in data:
            overlay.position_x = data['position_x']
        if 'position_y' in data:
            overlay.position_y = data['position_y']
        if 'style' in data:
            overlay.style = data['style']
        if 'animation_in' in data:
            overlay.animation_in = data['animation_in']
        if 'animation_out' in data:
            overlay.animation_out = data['animation_out']
        if 'animation_duration' in data:
            overlay.animation_duration = data['animation_duration']

        overlay.save()

        return JsonResponse({
            'success': True,
            'overlay': {
                'id': overlay.id,
                'text': overlay.text,
                'start_time': overlay.start_time,
                'end_time': overlay.end_time,
                'position_x': overlay.position_x,
                'position_y': overlay.position_y,
                'style': overlay.style,
            }
        })

    except Exception as e:
        logger.error(f"Update text overlay error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

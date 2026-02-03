# streamrec/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging
import base64
import os
from django.conf import settings

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    """
    StreamRec Dashboard - Overview of multi-stream video recording capabilities
    Complete interface with all features implemented
    """
    context = {
        'title': 'StreamRec - Multi-Stream Video Aufnahme',
        'features': [
            'Kamera-Stream Erfassung',
            'Bildschirm-Stream Erfassung', 
            'Multi-Monitor Unterstützung',
            'Live Komposition Vorschau',
            'Server Video-Speicherung',
            'Audio Studio - Professionelle Aufnahme',
            'Drag & Drop Layout System',
            'Performance-Monitoring',
            'Mobile-Optimierung'
        ]
    }
    return render(request, 'streamrec/dashboard.html', context)

@login_required
def recording_studio(request):
    """
    Aufnahmestudio mit Multi-Kamera-Support
    """
    import time
    context = {
        'title': 'StreamRec - Studio',
        'max_duration_minutes': 3,
        'supported_formats': ['webm'],
        'canvas_aspect_ratio': '16:9',  # Default format
        'version': 'server-ready',
        'cache_bust': int(time.time()),  # Cache-busting parameter
        'features': {
            'multi_camera': ['Mehrere Kameras gleichzeitig', 'Grid Layout', 'Individuelle Steuerung'],
            'layouts': ['Picture-in-Picture', 'Side-by-Side', 'Grid', 'Stacked'],
            'recording': ['WebM Export', 'Live Vorschau', 'Pause/Resume']
        }
    }
    return render(request, 'streamrec/recording_studio_server_ready.html', context)

@login_required 
def recording_studio_self_contained(request):
    """
    Self-Contained recording interface - All JavaScript inline (for deployment debugging)
    No external JS dependencies - everything embedded in template
    """
    context = {
        'title': 'StreamRec - Self-Contained Studio',
        'max_duration_minutes': 3,
        'supported_formats': ['webm'],
        'canvas_aspect_ratio': '16:9',  # Default format
        'version': 'self-contained',
    }
    return render(request, 'streamrec/recording_studio_self_contained.html', context)

@login_required 
def recording_studio_server_ready(request):
    """
    Server-Ready recording interface - Optimized for PythonAnywhere deployment
    Complete standalone HTML with maximum compatibility
    """
    context = {
        'title': 'StreamRec - Server Edition',
        'max_duration_minutes': 3,
        'supported_formats': ['webm'],
        'canvas_aspect_ratio': '16:9',
        'version': 'server-ready',
    }
    return render(request, 'streamrec/recording_studio_server_ready.html', context)

@login_required
@require_http_methods(["POST"])
def test_camera_access(request):
    """
    API endpoint to test camera access permissions
    Returns success/error status for frontend
    """
    try:
        # This is a mock API - actual camera testing happens in JavaScript
        # Here we could log user attempts or check permissions
        user = request.user
        logger.info(f"User {user.username} testing camera access")
        
        return JsonResponse({
            'success': True,
            'message': 'Kamera-Zugriff kann getestet werden',
            'instructions': 'Verwenden Sie getUserMedia() im Browser'
        })
    except Exception as e:
        logger.error(f"Camera access test error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Testen des Kamera-Zugriffs'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def test_screen_access(request):
    """
    API endpoint to test screen capture permissions
    """
    try:
        user = request.user
        logger.info(f"User {user.username} testing screen capture")
        
        return JsonResponse({
            'success': True,
            'message': 'Bildschirm-Aufnahme kann getestet werden',
            'instructions': 'Verwenden Sie getDisplayMedia() im Browser'
        })
    except Exception as e:
        logger.error(f"Screen access test error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Testen der Bildschirm-Aufnahme'
        }, status=500)

@login_required
def get_media_devices(request):
    """
    API endpoint to support media device enumeration
    Returns device information for frontend selection
    """
    try:
        # This returns mock data - actual device enumeration happens in JavaScript
        return JsonResponse({
            'success': True,
            'message': 'Geräte-Aufzählung verfügbar',
            'instructions': 'Verwenden Sie navigator.mediaDevices.enumerateDevices()'
        })
    except Exception as e:
        logger.error(f"Media devices error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Aufzählen der Mediengeräte'
        }, status=500)

@login_required 
def audio_recording_studio(request):
    """
    Dedicated Audio Recording Studio
    """
    context = {
        'title': 'StreamRec - Audio Studio',
        'max_duration_minutes': 10,
        'supported_formats': ['webm', 'wav', 'mp3'],
        'version': 'audio-studio',
        'features': {
            'recording': ['High-Quality Audio', 'Real-time Monitoring', 'Multiple Formats'],
            'visualization': ['Waveform Display', 'Level Meters', 'Spectrum Analyzer'],
            'processing': ['Auto Gain Control', 'Noise Reduction', 'Echo Cancellation']
        }
    }
    return render(request, 'streamrec/audio_recording_studio.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def save_audio_recording(request):
    """
    Save audio recording to server
    """
    try:
        data = json.loads(request.body)
        audio_data = data.get('audio_data')
        filename = data.get('filename', 'recording.webm')

        if not audio_data:
            return JsonResponse({
                'success': False,
                'error': 'Keine Audio-Daten erhalten'
            }, status=400)

        # Decode base64 audio data
        if audio_data.startswith('data:'):
            audio_data = audio_data.split(',', 1)[1]

        audio_bytes = base64.b64decode(audio_data)
        file_size = len(audio_bytes)

        # Check storage quota BEFORE saving
        from streamrec.storage_helpers import check_storage_quota, track_recording_upload
        from core.storage_service import StorageQuotaExceeded

        has_space, available, error_msg = check_storage_quota(request.user, file_size)
        if not has_space:
            return JsonResponse({
                'success': False,
                'error': f'Speicherlimit erreicht. {error_msg}',
                'quota_exceeded': True
            }, status=413)  # 413 Payload Too Large

        # Create media directory if it doesn't exist
        media_dir = os.path.join(settings.MEDIA_ROOT, 'audio_recordings')
        os.makedirs(media_dir, exist_ok=True)

        # Save the file
        file_path = os.path.join(media_dir, f"{request.user.id}_{filename}")
        with open(file_path, 'wb') as f:
            f.write(audio_bytes)

        # Track storage usage
        try:
            track_recording_upload(request.user, file_size, filename, recording_type='audio')
        except StorageQuotaExceeded as e:
            # Sollte nicht passieren da wir vorher geprüft haben, aber zur Sicherheit
            os.remove(file_path)  # Datei wieder löschen
            return JsonResponse({
                'success': False,
                'error': str(e),
                'quota_exceeded': True
            }, status=413)

        logger.info(f"Audio recording saved: {file_path} ({file_size} bytes)")

        return JsonResponse({
            'success': True,
            'message': 'Audio-Aufnahme erfolgreich gespeichert',
            'filename': filename,
            'file_size': file_size
        })

    except Exception as e:
        logger.error(f"Audio save error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Speichern der Audio-Aufnahme'
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def save_video_recording(request):
    """
    Save video recording to server and create Video object in database
    """
    try:
        data = json.loads(request.body)
        video_data = data.get('video_data')
        title = data.get('title', 'StreamRec Aufnahme')
        filename = data.get('filename', 'recording.webm')

        if not video_data:
            return JsonResponse({
                'success': False,
                'error': 'Keine Video-Daten erhalten'
            }, status=400)

        # Decode base64 video data
        if video_data.startswith('data:'):
            video_data = video_data.split(',', 1)[1]

        video_bytes = base64.b64decode(video_data)
        file_size = len(video_bytes)

        # Check storage quota BEFORE saving
        from streamrec.storage_helpers import check_storage_quota, track_recording_upload
        from core.storage_service import StorageQuotaExceeded
        from videos.models import Video
        from django.core.files.base import ContentFile
        import uuid
        from django.utils import timezone

        has_space, available, error_msg = check_storage_quota(request.user, file_size)
        if not has_space:
            return JsonResponse({
                'success': False,
                'error': f'Speicherlimit erreicht. {error_msg}',
                'quota_exceeded': True
            }, status=413)  # 413 Payload Too Large

        # Generate unique filename
        ext = filename.split('.')[-1] if '.' in filename else 'webm'
        unique_filename = f"{uuid.uuid4()}.{ext}"

        # Create Video object with the recording
        video = Video(
            user=request.user,
            title=title or f"StreamRec Aufnahme {timezone.now().strftime('%d.%m.%Y %H:%M')}",
            description=f"Aufgenommen mit StreamRec am {timezone.now().strftime('%d.%m.%Y um %H:%M Uhr')}",
            file_size=file_size,
        )

        # Save the video file through Django's file handling
        video.video_file.save(unique_filename, ContentFile(video_bytes), save=True)

        # Track storage usage
        try:
            track_recording_upload(request.user, file_size, filename, recording_type='video')
        except StorageQuotaExceeded as e:
            # Sollte nicht passieren da wir vorher geprüft haben, aber zur Sicherheit
            video.delete()  # Video wieder löschen
            return JsonResponse({
                'success': False,
                'error': str(e),
                'quota_exceeded': True
            }, status=413)

        logger.info(f"Video recording saved: {video.video_file.path} ({file_size} bytes) - Video ID: {video.id}")

        return JsonResponse({
            'success': True,
            'message': 'Video-Aufnahme erfolgreich gespeichert',
            'filename': filename,
            'file_size': file_size,
            'video_id': video.id,
            'video_url': video.get_absolute_url()
        })

    except Exception as e:
        logger.error(f"Video save error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Speichern der Video-Aufnahme'
        }, status=500)

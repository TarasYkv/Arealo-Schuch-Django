# streamrec/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    """
    StreamRec Dashboard - Overview of multi-stream video recording capabilities
    Phase 1: Basic interface with stream testing options
    """
    context = {
        'title': 'StreamRec - Multi-Stream Video Aufnahme',
        'phase': 1,
        'features': [
            'Kamera-Stream Erfassung',
            'Bildschirm-Stream Erfassung', 
            'Multi-Monitor Unterstützung',
            'Live Komposition Vorschau',
        ]
    }
    return render(request, 'streamrec/dashboard.html', context)

@login_required 
def recording_studio(request):
    """
    Main recording interface - All Phases: Complete multi-stream recording
    Implements WebRTC getUserMedia and getDisplayMedia APIs with advanced features
    """
    context = {
        'title': 'StreamRec - Professionelles Aufnahme Studio',
        'max_duration_minutes': 3,
        'supported_formats': ['webm', 'mp4'],
        'canvas_aspect_ratio': '9:16',
        'phases_active': [1, 2, 3, 4],
        'features': {
            'phase1': ['WebRTC Stream Capture', 'Canvas Composition'],
            'phase2': ['Layout Manager', 'Drag & Drop', 'Preset Layouts'],
            'phase3': ['MediaRecorder API', 'Duration Limits', 'Quality Settings'],
            'phase4': ['German Localization', 'Accessibility', 'Help System']
        }
    }
    return render(request, 'streamrec/recording_studio_enhanced.html', context)

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
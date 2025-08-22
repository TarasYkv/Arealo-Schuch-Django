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
            'Drag & Drop Layout System',
            'Performance-Monitoring',
            'Mobile-Optimierung'
        ]
    }
    return render(request, 'streamrec/dashboard.html', context)

@login_required 
def recording_studio(request):
    """
    Performance Optimized Aufnahmestudio - Anti-Freeze Technology
    """
    context = {
        'title': 'StreamRec - Studio',
        'max_duration_minutes': 3,
        'supported_formats': ['webm'],
        'canvas_aspect_ratio': '9:16',
        'version': 'performance-optimized',
        'features': {
            'anti_freeze': ['Frame Skip Logic', 'Video Element Pooling', 'Smart Rendering'],
            'performance': ['Adaptive FPS', 'Memory Management', 'Error Recovery'],
            'monitoring': ['Real-time FPS Counter', 'Dropped Frame Tracking', 'Render Time Analysis']
        }
    }
    return render(request, 'streamrec/recording_studio_performance_optimized.html', context)

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
        'canvas_aspect_ratio': '9:16',
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

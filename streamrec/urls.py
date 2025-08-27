# streamrec/urls.py

from django.urls import path
from . import views

app_name = 'streamrec'

urlpatterns = [
    # Dashboard - main entry point
    path('', views.dashboard, name='dashboard'),
    
    # Multi-stream recording studio
    path('aufnahme/', views.recording_studio, name='recording_studio'),
    
    # Self-Contained Version (for deployment debugging)
    path('aufnahme-self-contained/', views.recording_studio_self_contained, name='recording_studio_self_contained'),
    
    # Server-Ready Version (optimized for PythonAnywhere)
    path('aufnahme-server/', views.recording_studio_server_ready, name='recording_studio_server_ready'),
    
    # Audio recording studio
    path('audio-studio/', views.audio_recording_studio, name='audio_recording_studio'),
    
    # API endpoints for stream management
    path('api/test-camera/', views.test_camera_access, name='test_camera_access'),
    path('api/test-screen/', views.test_screen_access, name='test_screen_access'),
    path('api/get-devices/', views.get_media_devices, name='get_media_devices'),
    path('api/save-audio/', views.save_audio_recording, name='save_audio_recording'),
]
# streamrec/urls.py

from django.urls import path
from . import views

app_name = 'streamrec'

urlpatterns = [
    # Dashboard - main entry point
    path('', views.dashboard, name='dashboard'),
    
    # Phase 1: Basic stream capture
    path('aufnahme/', views.recording_studio, name='recording_studio'),
    
    # API endpoints for stream management
    path('api/test-camera/', views.test_camera_access, name='test_camera_access'),
    path('api/test-screen/', views.test_screen_access, name='test_screen_access'),
    path('api/get-devices/', views.get_media_devices, name='get_media_devices'),
    
    # Future phases
    # path('layouts/', views.layout_manager, name='layout_manager'),  # Phase 2
    # path('export/', views.export_video, name='export_video'),        # Phase 4
]
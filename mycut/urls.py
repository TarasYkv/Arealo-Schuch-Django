# mycut/urls.py

from django.urls import path
from . import views

app_name = 'mycut'

urlpatterns = [
    # Projekt-Verwaltung
    path('', views.project_list, name='list'),
    path('create/<int:video_id>/', views.create_project, name='create'),
    path('editor/<int:project_id>/', views.editor_view, name='editor'),
    path('delete/<int:project_id>/', views.delete_project, name='delete'),

    # API - Projekt
    path('api/project/<int:project_id>/', views.api_project_detail, name='api_project'),
    path('api/project/<int:project_id>/save/', views.api_save_project, name='api_save'),

    # API - AI-Funktionen
    path('api/project/<int:project_id>/transcribe/', views.api_transcribe, name='api_transcribe'),
    path('api/project/<int:project_id>/analyze/', views.api_analyze, name='api_analyze'),
    path('api/project/<int:project_id>/apply-suggestion/<int:suggestion_id>/', views.api_apply_suggestion, name='api_apply_suggestion'),
    path('api/project/<int:project_id>/reject-suggestion/<int:suggestion_id>/', views.api_reject_suggestion, name='api_reject_suggestion'),

    # API - Untertitel
    path('api/project/<int:project_id>/subtitles/', views.api_subtitles, name='api_subtitles'),
    path('api/project/<int:project_id>/subtitles/export/', views.api_export_subtitles, name='api_export_subtitles'),

    # API - Text-Overlays
    path('api/project/<int:project_id>/text-overlays/', views.api_text_overlays, name='api_text_overlays'),
    path('api/project/<int:project_id>/text-overlays/<int:overlay_id>/', views.api_text_overlay_detail, name='api_text_overlay_detail'),

    # API - Waveform
    path('api/project/<int:project_id>/waveform/', views.api_get_waveform, name='api_waveform'),

    # API - Export
    path('api/project/<int:project_id>/export/', views.api_start_export, name='api_export'),
    path('api/project/<int:project_id>/export/status/', views.api_export_status, name='api_export_status'),
]

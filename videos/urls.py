from django.urls import path
from . import views

app_name = 'videos'

urlpatterns = [
    # User views
    path('', views.video_list, name='list'),
    path('upload/', views.video_upload, name='upload'),
    path('detail/<int:video_id>/', views.video_detail, name='detail'),
    path('delete/<int:video_id>/', views.video_delete, name='delete'),
    path('storage/', views.storage_management, name='storage'),
    
    # Priority and archiving management
    path('priority/<int:video_id>/', views.set_video_priority, name='set_priority'),
    path('priorities/', views.video_priority_manager, name='priority_manager'),
    path('archived/', views.archived_videos, name='archived'),
    path('restore/<int:video_id>/', views.restore_video, name='restore'),
    path('optimizer/', views.storage_optimizer, name='optimizer'),
    
    # Public views
    path('v/<uuid:unique_id>/', views.video_view, name='view'),
    path('embed/<uuid:unique_id>/', views.video_embed, name='embed'),
    path('stream/<uuid:unique_id>/', views.video_stream, name='stream'),
    
    # API endpoints for StreamRec integration
    path('api/upload/', views.api_upload_video, name='api_upload'),
    path('api/storage-status/', views.api_storage_status, name='api_storage_status'),
]
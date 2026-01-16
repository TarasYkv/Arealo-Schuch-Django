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

    # Social Media Posting API
    path('api/social/generate/<int:video_id>/', views.api_generate_social_text, name='api_generate_social'),
    path('api/social/post/<int:video_id>/', views.api_post_to_social, name='api_post_social'),
    path('api/social/status/<int:video_id>/', views.api_social_status, name='api_social_status'),
    path('api/social/check-upload/<int:video_id>/', views.api_check_upload_status, name='api_check_upload_status'),

    # Chunked Upload API (for large files > 100MB)
    path('api/chunked/init/', views.api_chunked_upload_init, name='api_chunked_init'),
    path('api/chunked/chunk/', views.api_chunked_upload_chunk, name='api_chunked_chunk'),
    path('api/chunked/complete/', views.api_chunked_upload_complete, name='api_chunked_complete'),
    path('api/chunked/status/<uuid:upload_id>/', views.api_chunked_upload_status, name='api_chunked_status'),

    # Video Management API
    path('api/delete-videos/', views.api_delete_videos, name='api_delete_videos'),
]
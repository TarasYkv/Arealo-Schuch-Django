from django.urls import path
from . import views

app_name = 'videocreator'

urlpatterns = [
    # Main page
    path('', views.index, name='index'),
    
    # API endpoints
    path('api/projects/', views.projects_list, name='projects_list'),
    path('api/projects/<uuid:project_id>/', views.project_detail, name='project_detail'),
    
    # Assets
    path('api/projects/<uuid:project_id>/assets/', views.upload_asset, name='upload_asset'),
    path('api/projects/<uuid:project_id>/assets/<uuid:asset_id>/', views.delete_asset, name='delete_asset'),
    
    # Scenes
    path('api/projects/<uuid:project_id>/scenes/', views.create_scene, name='create_scene'),
    path('api/projects/<uuid:project_id>/scenes/<uuid:scene_id>/', views.scene_detail, name='scene_detail'),
    
    # Generation
    path('api/projects/<uuid:project_id>/generate/image/', views.generate_image, name='generate_image'),
    path('api/projects/<uuid:project_id>/scenes/<uuid:scene_id>/generate/video/', views.generate_video, name='generate_video'),
    path('api/projects/<uuid:project_id>/scenes/<uuid:scene_id>/generate/audio/', views.generate_audio, name='generate_audio'),
    
    # Export
    path('api/projects/<uuid:project_id>/export/', views.export_project, name='export_project'),
    
    # Task status
    path('api/task/<str:task_id>/', views.check_task, name='check_task'),
    
    # Callback
    path('api/callback/', views.callback, name='callback'),
]

from django.urls import path
from . import views

app_name = 'vidgen'

urlpatterns = [
    # Hauptseiten
    path('', views.vidgen_home, name='home'),
    path('neu/', views.create_single, name='create_single'),
    path('batch/', views.create_batch, name='create_batch'),
    
    # Listen
    path('projekte/', views.project_list, name='project_list'),
    path('batches/', views.batch_list, name='batch_list'),
    
    # Details
    path('projekt/<uuid:project_id>/', views.project_detail, name='project_detail'),
    path('batch/<uuid:batch_id>/', views.batch_detail, name='batch_detail'),
    
    # Regenerate
    path('projekt/<uuid:project_id>/regenerate/', views.regenerate_project, name='regenerate'),
    path('projekt/<uuid:project_id>/delete/', views.delete_project, name='delete_project'),
    path('api/projekt/<uuid:project_id>/status/', views.project_status_api, name='project_status_api'),
    path('api/batch/<uuid:batch_id>/status/', views.batch_status_api, name='batch_status_api'),
    path('api/imageforge/images/', views.imageforge_images_api, name='imageforge_images_api'),
    
    # Social Media Publishing
    path('api/projekt/<uuid:project_id>/generate-social-text/', views.generate_social_text, name='generate_social_text'),
    path('api/projekt/<uuid:project_id>/publish/', views.publish_video, name='publish_video'),
    
    # Quote & Fact Generators
    path('api/generate-quotes/', views.generate_quotes_api, name='generate_quotes'),
    path('api/generate-facts/', views.generate_facts_api, name='generate_facts'),

    # === MANUELLER WORKFLOW ===
    path('projekt/<uuid:project_id>/edit/', views.project_edit, name='project_edit'),
    path('api/projekt/<uuid:project_id>/step/script/', views.step_generate_script, name='step_script'),
    path('api/projekt/<uuid:project_id>/step/script/update/', views.step_update_script, name='step_update_script'),
    path('api/projekt/<uuid:project_id>/step/audio/', views.step_generate_audio, name='step_audio'),
    path('api/projekt/<uuid:project_id>/step/music/', views.step_generate_music, name='step_music'),
    # Musik-Bibliothek und Pixabay
    path('api/musik/bibliothek/', views.musik_bibliothek, name='musik_bibliothek'),
    path('api/musik/pixabay-suche/', views.pixabay_musik_suche, name='pixabay_suche'),
    path('api/projekt/<uuid:project_id>/musik-waehlen/', views.musik_waehlen, name='musik_waehlen'),
    path('api/projekt/<uuid:project_id>/musik-laden/', views.musik_laden, name='musik_laden'),
    path('api/musik/hochladen/', views.musik_hochladen, name='musik_hochladen'),
    path('api/projekt/<uuid:project_id>/step/clips/', views.step_fetch_clips, name='step_clips'),
    path('api/projekt/<uuid:project_id>/step/clips/search/', views.step_search_new_clip, name='step_search_clip'),
    path("api/projekt/<uuid:project_id>/task/<str:task_id>/status/", views.get_task_status, name="get_task_status"),
    path("api/projekt/<uuid:project_id>/task/<str:task_id>/status/", views.get_task_status, name="get_task_status"),
    path('api/projekt/<uuid:project_id>/step/render/', views.step_render_video, name='step_render'),
    path('api/projekt/<uuid:project_id>/clips/', views.get_project_clips, name='get_clips'),
    path('api/projekt/<uuid:project_id>/restart/', views.restart_from_step, name='restart_step'),
]

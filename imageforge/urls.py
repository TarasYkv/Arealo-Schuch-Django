from django.urls import path
from . import views

app_name = 'imageforge'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Generierung
    path('generate/', views.generate_image, name='generate'),

    # History
    path('history/', views.history, name='history'),
    path('generation/<int:generation_id>/', views.generation_detail, name='generation_detail'),
    path('generation/<int:generation_id>/delete/', views.delete_generation, name='delete_generation'),
    path('generation/<int:generation_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),

    # Charaktere
    path('characters/', views.character_list, name='character_list'),
    path('characters/create/', views.character_create, name='character_create'),
    path('characters/<int:character_id>/', views.character_detail, name='character_detail'),
    path('characters/<int:character_id>/edit/', views.character_edit, name='character_edit'),
    path('characters/<int:character_id>/delete/', views.character_delete, name='character_delete'),

    # Presets
    path('presets/', views.preset_list, name='preset_list'),
    path('presets/save/', views.save_preset, name='save_preset'),
    path('presets/<int:preset_id>/delete/', views.delete_preset, name='delete_preset'),

    # Mockup-Text Feature
    path('mockups/', views.mockup_list, name='mockup_list'),
    path('mockups/<int:mockup_id>/', views.mockup_detail, name='mockup_detail'),
    path('mockups/<int:mockup_id>/delete/', views.mockup_delete, name='mockup_delete'),
    path('mockups/<int:mockup_id>/json/', views.mockup_json, name='mockup_json'),
    path('mockups/<int:mockup_id>/favorite/', views.toggle_mockup_favorite, name='toggle_mockup_favorite'),
    path('generate/mockup/', views.generate_mockup, name='generate_mockup'),
    path('generate/mockup-scene/', views.generate_mockup_scene, name='generate_mockup_scene'),
]

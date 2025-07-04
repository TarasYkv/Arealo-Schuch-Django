from django.urls import path
from . import views

app_name = 'naturmacher'

urlpatterns = [
    path('', views.ThemaListView.as_view(), name='thema_list'),
    path('thema/<int:pk>/', views.ThemaDetailView.as_view(), name='thema_detail'),
    path('training/<int:pk>/', views.TrainingDetailView.as_view(), name='training_detail'),
    path('training/<int:training_id>/toggle/', views.toggle_training_status, name='toggle_training_status'),
    path('upload/', views.upload_trainings_view, name='upload_trainings'),
    path('import/', views.import_trainings_view, name='import_trainings'),
    path('training/<int:training_id>/notizen/get/', views.get_training_notizen, name='get_training_notizen'),
    path('training/<int:training_id>/notizen/save/', views.save_training_notizen, name='save_training_notizen'),
    path('training/<int:training_id>/youtube/save/', views.save_youtube_links, name='save_youtube_links'),
    path('thema/<int:thema_id>/notizen/', views.get_thema_notizen, name='get_thema_notizen'),
    path('search/', views.search_themen_und_trainings, name='search'),
    path('ai-training/generate/', views.generate_ai_training, name='generate_ai_training'),
    path('training/<int:training_id>/delete/', views.delete_training, name='delete_training'),
    path('thema/create/', views.create_thema, name='create_thema'),
    path('thema/<int:thema_id>/delete/', views.delete_thema, name='delete_thema'),
    
    # API Balance Management
    path('api/balances/', views.get_api_balances, name='get_api_balances'),
    path('api/balances/update/', views.update_api_balance, name='update_api_balance'),
    path('api/balances/remove-key/', views.remove_api_key, name='remove_api_key'),
    path('api/usage/stats/', views.get_usage_statistics, name='get_usage_statistics'),
    path('api/estimate-cost/', views.estimate_training_cost, name='estimate_training_cost'),
    
    # Table of contents editing
    path('thema/<int:thema_id>/inhaltsverzeichnis/save/', views.save_inhaltsverzeichnis, name='save_inhaltsverzeichnis'),
    
    # API key validation
    path('api/validate-key/', views.validate_api_key, name='validate_api_key'),
]
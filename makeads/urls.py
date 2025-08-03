from django.urls import path
from . import views, views_ajax

app_name = 'makeads'

urlpatterns = [
    # Dashboard und Übersicht
    path('', views.dashboard, name='dashboard'),
    path('campaigns/', views.campaign_list, name='campaign_list'),
    
    # 3-Schritt Wizard für Campaign-Erstellung
    path('create/step1/', views.campaign_create_step1, name='campaign_create_step1'),
    path('create/step2/', views.campaign_create_step2, name='campaign_create_step2'),
    path('create/step3/', views.campaign_create_step3, name='campaign_create_step3'),
    
    # Campaign Management
    path('campaign/<uuid:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('campaign/<uuid:campaign_id>/delete/', views.campaign_delete, name='campaign_delete'),
    path('campaign/<uuid:campaign_id>/generate-more/', views.generate_more_creatives, name='generate_more_creatives'),
    
    # Creative Management
    path('creative/<uuid:creative_id>/', views.creative_detail, name='creative_detail'),
    path('creative/<uuid:creative_id>/revise/', views.creative_revise, name='creative_revise'),
    path('creative/<uuid:creative_id>/toggle-favorite/', views.creative_toggle_favorite, name='creative_toggle_favorite'),
    
    # Bulk Actions
    path('bulk-actions/', views.bulk_actions, name='bulk_actions'),
    
    # AJAX Endpoints
    path('job/<uuid:job_id>/status/', views.job_status, name='job_status'),
    path('ajax/start-generation/', views_ajax.start_generation_ajax, name='start_generation_ajax'),
    path('ajax/cancel-generation/<uuid:job_id>/', views_ajax.cancel_generation_ajax, name='cancel_generation_ajax'),
    path('ajax/active-jobs/', views_ajax.active_jobs_ajax, name='active_jobs_ajax'),
    path('ajax/generation-stats/', views_ajax.generation_stats_ajax, name='generation_stats_ajax'),
]
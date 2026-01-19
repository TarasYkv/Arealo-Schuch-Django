from django.urls import path
from . import views

app_name = 'backloom'

urlpatterns = [
    # Dashboard
    path('', views.BackloomDashboardView.as_view(), name='dashboard'),

    # Feed
    path('feed/', views.BackloomFeedView.as_view(), name='feed'),

    # Detail
    path('source/<uuid:pk>/', views.BackloomSourceDetailView.as_view(), name='source_detail'),

    # Suchhistorie
    path('history/', views.BackloomSearchHistoryView.as_view(), name='search_history'),

    # API Endpoints
    path('api/search/start/', views.api_start_search, name='api_start_search'),
    path('api/search/<uuid:pk>/status/', views.api_search_status, name='api_search_status'),
    path('api/source/<uuid:pk>/status/', views.api_update_source_status, name='api_update_source_status'),
    path('api/source/<uuid:pk>/notes/', views.api_update_source_notes, name='api_update_source_notes'),
    path('api/sources/delete/', views.api_delete_sources, name='api_delete_sources'),
    path('api/init-queries/', views.api_init_queries, name='api_init_queries'),
    path('api/cleanup/', views.api_cleanup_old, name='api_cleanup'),
    path('api/cleanup-stats/', views.api_cleanup_stats, name='api_cleanup_stats'),
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/health-check/', views.api_health_check, name='api_health_check'),
    path('api/search-progress/', views.api_search_progress, name='api_search_progress'),

    # Suchbegriffe CRUD
    path('api/queries/', views.api_get_queries, name='api_get_queries'),
    path('api/queries/add/', views.api_add_query, name='api_add_query'),
    path('api/queries/update/', views.api_update_query, name='api_update_query'),
    path('api/queries/delete/', views.api_delete_query, name='api_delete_query'),
    path('api/queries/toggle/', views.api_toggle_query, name='api_toggle_query'),
]

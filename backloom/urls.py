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
    path('api/init-queries/', views.api_init_queries, name='api_init_queries'),
    path('api/cleanup/', views.api_cleanup_old, name='api_cleanup'),
    path('api/stats/', views.api_stats, name='api_stats'),
]

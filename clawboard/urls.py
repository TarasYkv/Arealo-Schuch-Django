from django.urls import path
from . import views

app_name = 'clawboard'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Connections
    path('connections/', views.connection_list, name='connection_list'),
    path('connections/add/', views.connection_add, name='connection_add'),
    path('connections/<int:pk>/', views.connection_detail, name='connection_detail'),
    path('connections/<int:pk>/edit/', views.connection_edit, name='connection_edit'),
    path('connections/<int:pk>/delete/', views.connection_delete, name='connection_delete'),
    path('connections/<int:pk>/test/', views.connection_test, name='connection_test'),

    # Projects
    path('projects/', views.project_list, name='project_list'),
    path('projects/add/', views.project_add, name='project_add'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),

    # Conversations
    path('conversations/', views.conversation_list, name='conversation_list'),
    path('conversations/<int:pk>/', views.conversation_detail, name='conversation_detail'),

    # Memory Files
    path('memory/', views.memory_browser, name='memory_browser'),
    path('memory/file/', views.memory_file_view, name='memory_file_view'),
    path('memory/file/save/', views.memory_file_save, name='memory_file_save'),

    # Scheduled Tasks
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),

    # Integrations
    path('integrations/', views.integration_list, name='integration_list'),

    # API Endpoints
    path('api/status/', views.api_status, name='api_status'),
    path('api/sync/', views.api_sync, name='api_sync'),
    path('api/push/', views.api_connector_push, name='api_push'),
    path('api/dashboard/', views.api_dashboard_refresh, name='api_dashboard_refresh'),
]

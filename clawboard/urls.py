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

    # Connector
    path('connector/', views.connector_setup, name='connector_setup'),
    path('connector/download/', views.connector_download_script, name='connector_download_script'),
    path('connector/cfg/<str:token>/', views.connector_config_token, name='connector_config_token'),
    path('connector/config/<int:pk>/', views.connector_download_config, name='connector_download_config'),

    # KI Chat
    path('chat/', views.chat_view, name='chat'),
    path('chat/<int:pk>/', views.chat_view, name='chat_detail'),

    # API Endpoints
    path('api/status/', views.api_status, name='api_status'),
    path('api/sync/', views.api_sync, name='api_sync'),
    path('api/push/', views.api_connector_push, name='api_push'),
    path('api/dashboard/', views.api_dashboard_refresh, name='api_dashboard_refresh'),
    path('api/connector/restart/', views.api_connector_restart, name='api_connector_restart'),

    # Chat API
    path('api/chat/create/', views.api_chat_create, name='api_chat_create'),
    path('api/chat/send/', views.api_chat_send, name='api_chat_send'),
    path('api/chat/poll/', views.api_chat_poll, name='api_chat_poll'),
    path('api/chat/<int:pk>/messages/', views.api_chat_messages, name='api_chat_messages'),
    path('api/chat/<int:pk>/delete/', views.api_chat_delete, name='api_chat_delete'),

    # Gateway API
    path('api/gateway/models/', views.api_gateway_models, name='api_gateway_models'),
]

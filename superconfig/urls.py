from django.urls import path
from . import views

app_name = 'superconfig'

urlpatterns = [
    path('', views.superconfig_dashboard, name='dashboard'),
    path('backup/', views.database_backup, name='database_backup'),
    path('restore/', views.database_restore, name='database_restore'),
    path('restore/server/', views.database_restore_from_server, name='database_restore_from_server'),
    path('backups/list/', views.list_backups, name='list_backups'),
    path('backups/delete/', views.delete_backup, name='delete_backup'),
    path('backups/download/<str:filename>/', views.download_backup, name='download_backup'),
    path('database/info/', views.database_info, name='database_info'),
    path('email/status/', views.email_service_status, name='email_service_status'),
    path('email/test/', views.test_email_service, name='test_email_service'),
    path('email/config/', views.update_email_config, name='update_email_config'),
    path('email/config/save/', views.save_email_config, name='save_email_config'),
    path('email/shared/add/', views.add_shared_email, name='add_shared_email'),
    path('email/diagnostics/', views.email_network_diagnostics, name='email_network_diagnostics'),
    path('email/auto-configure/', views.auto_configure_email_fallback, name='auto_configure_email_fallback'),
    path('zoho/setup/', views.setup_zoho_oauth, name='setup_zoho_oauth'),
    path('zoho/callback/', views.zoho_oauth_callback, name='zoho_oauth_callback'),

    # Global Messages URLs
    path('messages/create/', views.create_global_message, name='create_global_message'),
    path('messages/list/', views.list_global_messages, name='list_global_messages'),
    path('messages/<int:message_id>/toggle/', views.toggle_message_status, name='toggle_message_status'),
    path('messages/<int:message_id>/delete/', views.delete_global_message, name='delete_global_message'),
    path('messages/<int:message_id>/preview/', views.get_message_for_preview, name='get_message_for_preview'),
    path('messages/active/', views.get_active_messages_for_user, name='get_active_messages_for_user'),

    # Debug Settings URLs
    path('debug/settings/', views.get_debug_settings, name='get_debug_settings'),
    path('debug/settings/update/', views.update_debug_settings, name='update_debug_settings'),

    # User Management URLs
    path('users/list/', views.get_available_users, name='get_available_users'),
]
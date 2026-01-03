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

    # Storage & Subscription API URLs
    path('api/storage/statistics/', views.storage_statistics_api, name='storage_statistics_api'),
    path('api/storage/top-users/', views.top_storage_users_api, name='top_storage_users_api'),
    path('api/storage/by-app/', views.storage_by_app_api, name='storage_by_app_api'),
    path('api/storage/user/<int:user_id>/', views.user_storage_detail_api, name='user_storage_detail_api'),
    path('api/storage/logs/', views.recent_storage_logs_api, name='recent_storage_logs_api'),
    path('api/subscription/plans-overview/', views.subscription_plans_overview_api, name='subscription_plans_overview_api'),

    # Google OAuth URLs
    path('api/google-oauth/status/', views.google_oauth_status, name='google_oauth_status'),
    path('api/google-oauth/save/', views.save_google_oauth, name='save_google_oauth'),
    path('api/google-oauth/delete/', views.delete_google_oauth, name='delete_google_oauth'),
    path('api/google-oauth/test/', views.test_google_oauth, name='test_google_oauth'),

    # API Provider Settings URLs
    path('api/providers/list/', views.api_providers_list, name='api_providers_list'),
    path('api/providers/save/', views.api_providers_save, name='api_providers_save'),

    # Social Page (Link in Bio) URLs
    path('api/social/config/', views.social_page_config, name='social_page_config'),
    path('api/social/config/save/', views.social_page_config_save, name='social_page_config_save'),
    path('api/social/upload-image/', views.social_page_upload_image, name='social_page_upload_image'),
    path('api/social/icon/add/', views.social_icon_add, name='social_icon_add'),
    path('api/social/icon/<int:icon_id>/update/', views.social_icon_update, name='social_icon_update'),
    path('api/social/icon/<int:icon_id>/delete/', views.social_icon_delete, name='social_icon_delete'),
    path('api/social/icon/reorder/', views.social_icon_reorder, name='social_icon_reorder'),
    path('api/social/button/add/', views.social_button_add, name='social_button_add'),
    path('api/social/button/<int:button_id>/update/', views.social_button_update, name='social_button_update'),
    path('api/social/button/<int:button_id>/delete/', views.social_button_delete, name='social_button_delete'),
    path('api/social/button/reorder/', views.social_button_reorder, name='social_button_reorder'),
    path('api/social/stats/', views.social_page_stats, name='social_page_stats'),
]
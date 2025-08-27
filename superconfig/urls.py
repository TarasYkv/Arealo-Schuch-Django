from django.urls import path
from . import views

app_name = 'superconfig'

urlpatterns = [
    path('', views.superconfig_dashboard, name='dashboard'),
    path('backup/', views.database_backup, name='database_backup'),
    path('restore/', views.database_restore, name='database_restore'),
    path('restore/server/', views.database_restore_from_server, name='database_restore_from_server'),
    path('backups/list/', views.list_backups, name='list_backups'),
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
]
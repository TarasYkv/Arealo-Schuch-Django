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
]
"""
Android APK Manager URLs
REST API, Web Interface und Public Pages
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .viewsets import (
    AndroidAppViewSet,
    AppVersionViewSet,
    PublicAPIViewSet,
    DownloadLogViewSet
)

# App namespace
app_name = 'android_apk_manager'

# REST API Router
router = DefaultRouter()
router.register(r'apps', AndroidAppViewSet, basename='app')
router.register(r'versions', AppVersionViewSet, basename='version')
router.register(r'public', PublicAPIViewSet, basename='public-api')
router.register(r'download-logs', DownloadLogViewSet, basename='downloadlog')

urlpatterns = [
    # ===== REST API =====
    path('api/', include(router.urls)),

    # ===== APK Download =====
    path('download/<uuid:version_id>/', views.download_apk, name='download-apk'),

    # ===== Web Interface (Owner) =====
    path('', views.dashboard, name='dashboard'),
    path('app/<uuid:app_id>/', views.app_detail, name='app_detail'),
    path('app/<uuid:app_id>/toggle-public/', views.toggle_app_public, name='toggle_app_public'),
    path('app/<uuid:app_id>/delete/', views.delete_app, name='delete_app'),

    # ===== Public Pages =====
    path('public/', views.public_app_list, name='public_app_list'),
    path('public/<uuid:app_id>/', views.public_app_detail, name='public_app_detail'),
]

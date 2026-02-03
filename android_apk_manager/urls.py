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
    path('create-app/', views.create_app, name='create_app'),
    path('upload-version/', views.upload_version, name='upload_version'),
    path('upload-version/<uuid:app_id>/', views.upload_version, name='upload_version_for_app'),
    path('app/<uuid:app_id>/', views.app_detail, name='app_detail'),
    path('app/<uuid:app_id>/edit/', views.edit_app, name='edit_app'),
    path('app/<uuid:app_id>/toggle-public/', views.toggle_app_public, name='toggle_app_public'),
    path('app/<uuid:app_id>/delete/', views.delete_app, name='delete_app'),
    path('version/<uuid:version_id>/edit/', views.edit_version, name='edit_version'),
    path('version/<uuid:version_id>/delete/', views.delete_version, name='delete_version'),

    # ===== Screenshots =====
    path('app/<uuid:app_id>/screenshots/upload/', views.upload_screenshots, name='upload_screenshots'),
    path('screenshot/<uuid:screenshot_id>/delete/', views.delete_screenshot, name='delete_screenshot'),
    path('app/<uuid:app_id>/screenshots/reorder/', views.reorder_screenshots, name='reorder_screenshots'),

    # ===== Public Pages =====
    path('public/', views.public_app_list, name='public_app_list'),
    path('public/<uuid:app_id>/', views.public_app_detail, name='public_app_detail'),
]

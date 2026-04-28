from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .viewsets import (
    MagvisImageAssetViewSet,
    MagvisProjectViewSet,
    MagvisTopicQueueViewSet,
)

app_name = 'magvis'

router = DefaultRouter()
router.register(r'projects', MagvisProjectViewSet, basename='magvis-project')
router.register(r'images', MagvisImageAssetViewSet, basename='magvis-image')
router.register(r'topics', MagvisTopicQueueViewSet, basename='magvis-topic')

urlpatterns = [
    # Wizard
    path('', views.project_list, name='project_list'),
    path('neu/', views.project_create, name='project_create'),
    path('projekt/<uuid:project_id>/', views.project_detail, name='project_detail'),
    path('projekt/<uuid:project_id>/advance/', views.project_advance, name='project_advance'),
    path('projekt/<uuid:project_id>/status/', views.project_status, name='project_status'),
    path('projekt/<uuid:project_id>/bild/<int:asset_id>/posten/', views.image_post, name='image_post'),

    # Settings + Report
    path('einstellungen/', views.settings_view, name='settings'),
    path('einstellungen/report/', views.report_config_view, name='report_config'),
    path('einstellungen/api/providers/', views.api_available_providers, name='api_available_providers'),

    # Topics
    path('themen/', views.topics_list, name='topics_list'),
    path('themen/neu/', views.topic_create, name='topic_create'),
    path('themen/<int:topic_id>/bearbeiten/', views.topic_edit, name='topic_edit'),
    path('themen/<int:topic_id>/loeschen/', views.topic_delete, name='topic_delete'),
    path('themen/import/', views.topic_bulk_import, name='topic_bulk_import'),

    # API
    path('api/', include(router.urls)),
]

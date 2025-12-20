"""VSkript URL Configuration"""

from django.urls import path
from . import views

app_name = 'vskript'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # CRUD
    path('create/', views.project_create, name='create'),
    path('<uuid:project_id>/', views.project_detail, name='detail'),
    path('<uuid:project_id>/delete/', views.project_delete, name='delete'),

    # Script API
    path('api/generate/', views.api_generate, name='api_generate'),
    path('api/regenerate/<uuid:project_id>/', views.api_regenerate, name='api_regenerate'),

    # Image API
    path('api/images/generate/<uuid:project_id>/', views.api_generate_images, name='api_generate_images'),
    path('api/images/generate-single/<uuid:image_id>/', views.api_generate_single_image, name='api_generate_single_image'),
    path('api/images/regenerate/<uuid:image_id>/', views.api_regenerate_image, name='api_regenerate_image'),
    path('api/images/download/<uuid:image_id>/', views.api_download_image, name='api_download_image'),
    path('api/images/download-all/<uuid:project_id>/', views.api_download_all_images, name='api_download_all_images'),
    path('api/images/delete/<uuid:image_id>/', views.api_delete_image, name='api_delete_image'),
    path('api/images/delete-all/<uuid:project_id>/', views.api_delete_all_images, name='api_delete_all_images'),
]

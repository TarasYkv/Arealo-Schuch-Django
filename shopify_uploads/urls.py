from django.urls import path
from . import views

app_name = 'shopify_uploads'

urlpatterns = [
    # Web-Interface für Superuser
    path('', views.image_list, name='image_list'),
    path('<str:unique_id>/', views.image_detail, name='image_detail'),
    path('<str:unique_id>/delete/', views.image_delete, name='image_delete'),

    # API-Endpoints
    path('api/upload/', views.upload_image, name='api_upload'),
    path('api/get/<str:unique_id>/', views.get_image, name='api_get'),
]

from django.urls import path
from . import views

app_name = 'shopify_uploads'

urlpatterns = [
    # API-Endpoints (müssen VOR den parametrisierten Routen stehen!)
    path('api/upload/', views.upload_image, name='api_upload'),
    path('api/get/<str:unique_id>/', views.get_image, name='api_get'),
    path('api/webhook/order-created/', views.shopify_order_webhook, name='shopify_order_webhook'),

    # Web-Interface für Superuser
    path('', views.image_list, name='image_list'),
    path('<str:unique_id>/', views.image_detail, name='image_detail'),
    path('<str:unique_id>/delete/', views.image_delete, name='image_delete'),
]

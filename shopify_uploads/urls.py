from django.urls import path, re_path
from . import views

app_name = 'shopify_uploads'

urlpatterns = [
    # API-Endpoints (müssen VOR den parametrisierten Routen stehen!)
    path('api/upload/', views.upload_image, name='api_upload'),
    path('api/get/<str:unique_id>/', views.get_image, name='api_get'),
    path('api/webhook/order-created/', views.shopify_order_webhook, name='shopify_order_webhook'),

    # Media-Proxy für CORS (PythonAnywhere Workaround)
    re_path(r'^media/(?P<file_path>.+)$', views.serve_media_with_cors, name='serve_media'),

    # Web-Interface für Superuser
    path('', views.image_list, name='image_list'),
    path('<str:unique_id>/', views.image_detail, name='image_detail'),
    path('<str:unique_id>/edit/', views.image_edit, name='image_edit'),
    path('<str:unique_id>/process/', views.process_image_ajax, name='process_image_ajax'),
    path('<str:unique_id>/save/', views.save_processed_image, name='save_processed_image'),
    path('<str:unique_id>/delete/', views.image_delete, name='image_delete'),
]

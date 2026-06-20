from django.urls import path
from . import views

app_name = 'voice_pot'

urlpatterns = [
    # Oeffentlich
    path('api/upload/', views.upload_audio, name='upload'),
    path('api/webhook/order-created/', views.order_webhook, name='order_webhook'),
    path('v/<str:unique_id>/', views.play, name='play'),

    # Admin (Superuser)
    path('', views.admin_list, name='admin_list'),
    path('a/<str:unique_id>/', views.admin_detail, name='admin_detail'),
    path('a/<str:unique_id>/action/', views.admin_action, name='admin_action'),
    path('a/<str:unique_id>/qr.png', views.qr_png, name='qr_png'),
]

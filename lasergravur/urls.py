"""URL-Routes für die Lasergravur-App."""
from django.urls import path

from . import views

app_name = 'lasergravur'

urlpatterns = [
    path('', views.OrderListView.as_view(), name='order_list'),
    path('<uuid:pk>/', views.order_editor, name='order_editor'),
    path('<uuid:pk>/preview.png', views.order_preview_png, name='order_preview_png'),
    path('<uuid:pk>/save/', views.order_save, name='order_save'),
    path('<uuid:pk>/download.png', views.order_download_png, name='order_download_png'),
    path('<uuid:pk>/mark-engraved/', views.order_mark_engraved, name='order_mark_engraved'),
    path('<uuid:pk>/status/', views.order_change_status, name='order_change_status'),
]

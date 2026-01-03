from django.urls import path
from . import views

app_name = 'linkloom'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # API Endpoints
    path('api/check-slug/', views.check_slug_availability, name='check_slug'),
    path('api/save/', views.save_page, name='save_page'),
    path('api/upload-image/', views.upload_image, name='upload_image'),
    path('api/delete/', views.delete_page, name='delete_page'),

    # Icon API
    path('api/icon/add/', views.icon_add, name='icon_add'),
    path('api/icon/<int:icon_id>/delete/', views.icon_delete, name='icon_delete'),
    path('api/icon/<int:icon_id>/toggle/', views.icon_toggle, name='icon_toggle'),

    # Button API
    path('api/button/add/', views.button_add, name='button_add'),
    path('api/button/<int:button_id>/update/', views.button_update, name='button_update'),
    path('api/button/<int:button_id>/delete/', views.button_delete, name='button_delete'),
    path('api/button/<int:button_id>/toggle/', views.button_toggle, name='button_toggle'),

    # Statistics
    path('api/stats/', views.get_stats, name='stats'),
]

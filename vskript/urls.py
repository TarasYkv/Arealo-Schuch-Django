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

    # API
    path('api/generate/', views.api_generate, name='api_generate'),
    path('api/regenerate/<uuid:project_id>/', views.api_regenerate, name='api_regenerate'),
]

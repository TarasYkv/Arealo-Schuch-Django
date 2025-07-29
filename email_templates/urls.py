from django.urls import path
from django.shortcuts import render
from . import views

app_name = 'email_templates'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Zoho Mail Connections
    path('connections/', views.connection_list, name='connection_list'),
    path('connections/create/', views.connection_create, name='connection_create'),
    path('connections/<int:pk>/', views.connection_detail, name='connection_detail'),
    path('connections/<int:pk>/edit/', views.connection_edit, name='connection_edit'),
    path('connections/<int:pk>/delete/', views.connection_delete, name='connection_delete'),
    path('connections/<int:pk>/test/', views.connection_test, name='connection_test'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('auth/callback/', views.oauth_callback, name='oauth_callback_alt'),
    
    # Email Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/preview/', views.template_preview, name='template_preview'),
    
    # Test Email
    path('test-email/', views.send_test_email, name='send_test_email'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # API Endpoints
    path('api/templates/<int:pk>/variables/', views.api_template_variables, name='api_template_variables'),
    path('api/templates/<int:pk>/render/', views.api_render_preview, name='api_render_preview'),
    
    # Debug (nur development)
    path('debug/urls/', lambda request: render(request, 'email_templates/debug_urls.html'), name='debug_urls'),
]
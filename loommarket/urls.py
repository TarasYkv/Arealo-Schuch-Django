from django.urls import path
from . import views

app_name = 'loommarket'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Business Management
    path('add/', views.add_business, name='add_business'),
    path('businesses/', views.business_list, name='business_list'),
    path('businesses/<int:pk>/', views.business_detail, name='business_detail'),
    path('businesses/<int:pk>/delete/', views.business_delete, name='business_delete'),

    # API: Instagram Search
    path('api/search-instagram/', views.api_search_instagram, name='api_search_instagram'),
    path('api/search-images/<int:business_id>/', views.api_search_images, name='api_search_images'),
    path('api/upload-image/<int:business_id>/', views.api_upload_image, name='api_upload_image'),
    path('api/delete-image/<int:image_id>/', views.api_delete_image, name='api_delete_image'),
    path('api/set-logo/<int:image_id>/', views.api_set_logo, name='api_set_logo'),
    path('api/refresh-instagram/<int:business_id>/', views.api_refresh_instagram, name='api_refresh_instagram'),
    path('api/refresh-impressum/<int:business_id>/', views.api_refresh_impressum, name='api_refresh_impressum'),

    # API: Slogan
    path('api/fonts/', views.api_get_fonts, name='api_get_fonts'),
    path('api/extract-slogans/<int:business_id>/', views.api_extract_slogans, name='api_extract_slogans'),
    path('api/generate-slogan-image/<int:business_id>/', views.api_generate_slogan_image, name='api_generate_slogan_image'),
    path('api/preview-slogan-fonts/<int:business_id>/', views.api_preview_slogan_fonts, name='api_preview_slogan_fonts'),

    # API: Logo + Text Kombination
    path('api/combo-layouts/', views.api_get_combo_layouts, name='api_get_combo_layouts'),
    path('api/combine-logo-text/<int:business_id>/', views.api_combine_logo_text, name='api_combine_logo_text'),

    # Mockup Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),

    # Campaigns
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/create/<int:business_id>/', views.campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),

    # API: Campaign Actions
    path('api/campaigns/<int:campaign_id>/generate-mockup/', views.api_generate_mockup, name='api_generate_mockup'),
    path('api/campaigns/<int:campaign_id>/generate-captions/', views.api_generate_captions, name='api_generate_captions'),

    # Posts
    path('api/posts/<int:post_id>/publish/', views.api_publish_post, name='api_publish_post'),
    path('posts/<int:post_id>/download/', views.download_post, name='download_post'),
    path('campaigns/<int:campaign_id>/download-all/', views.download_all, name='download_all'),
]

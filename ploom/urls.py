from django.urls import path
from . import views

app_name = 'ploom'

urlpatterns = [
    # Dashboard & Einstellungen
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),

    # Themes
    path('themes/', views.theme_list, name='theme_list'),
    path('themes/create/', views.theme_create, name='theme_create'),
    path('themes/<int:theme_id>/edit/', views.theme_edit, name='theme_edit'),
    path('themes/<int:theme_id>/delete/', views.theme_delete, name='theme_delete'),

    # Produkte
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<uuid:product_id>/edit/', views.product_edit, name='product_edit'),
    path('products/<uuid:product_id>/delete/', views.product_delete, name='product_delete'),
    path('products/<uuid:product_id>/duplicate/', views.product_duplicate, name='product_duplicate'),

    # Varianten API
    path('api/products/<uuid:product_id>/variants/add/', views.api_variant_add, name='api_variant_add'),
    path('api/products/<uuid:product_id>/variants/<int:variant_id>/update/', views.api_variant_update, name='api_variant_update'),
    path('api/products/<uuid:product_id>/variants/<int:variant_id>/delete/', views.api_variant_delete, name='api_variant_delete'),

    # Bilder API
    path('api/products/<uuid:product_id>/images/upload/', views.api_image_upload, name='api_image_upload'),
    path('api/products/<uuid:product_id>/images/reorder/', views.api_image_reorder, name='api_image_reorder'),
    path('api/products/<uuid:product_id>/images/<int:image_id>/delete/', views.api_image_delete, name='api_image_delete'),
    path('api/products/<uuid:product_id>/images/<int:image_id>/set-featured/', views.api_image_set_featured, name='api_image_set_featured'),
    path('api/products/<uuid:product_id>/images/from-imageforge/', views.api_image_from_imageforge, name='api_image_from_imageforge'),

    # ImageForge Integration
    path('api/imageforge/generations/', views.api_imageforge_generations, name='api_imageforge_generations'),
    path('api/imageforge/mockups/', views.api_imageforge_mockups, name='api_imageforge_mockups'),

    # KI-Generierung
    path('api/generate/title/', views.api_generate_title, name='api_generate_title'),
    path('api/generate/description/', views.api_generate_description, name='api_generate_description'),
    path('api/generate/seo/', views.api_generate_seo, name='api_generate_seo'),
    path('api/generate/tags/', views.api_generate_tags, name='api_generate_tags'),

    # Verlauf
    path('api/history/<str:field_type>/', views.api_history, name='api_history'),
    path('api/history/prices/', views.api_history_prices, name='api_history_prices'),
    path('api/favorite-price/add/', views.api_favorite_price_add, name='api_favorite_price_add'),

    # Shopify
    path('api/shopify/collections/', views.api_shopify_collections, name='api_shopify_collections'),
    path('api/shopify/upload/<uuid:product_id>/', views.api_shopify_upload, name='api_shopify_upload'),

    # Tests (nur Superuser)
    path('tests/', views.run_tests, name='run_tests'),
]

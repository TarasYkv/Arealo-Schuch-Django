from django.urls import path
from . import views

app_name = 'image_editor'

urlpatterns = [
    # Hauptseiten
    path('', views.dashboard_view, name='dashboard'),
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/edit/', views.ProjectEditView.as_view(), name='project_edit'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    
    # Bildbearbeitung
    path('projects/<int:pk>/editor/', views.image_editor_view, name='image_editor'),
    
    # AI-Bildgenerierung
    path('generate/', views.ai_generation_view, name='ai_generation'),
    path('generate/history/', views.ai_history_view, name='ai_history'),
    
    # API Endpoints
    path('api/upload/', views.upload_image_api, name='upload_image'),
    path('api/generate-ai/', views.generate_ai_image_api, name='generate_ai_image'),
    path('api/process-image/', views.process_image_api, name='process_image'),
    path('api/export/', views.export_image_api, name='export_image'),
    
    # Spezielle Funktionen
    path('api/remove-background/', views.remove_background_api, name='remove_background'),
    path('api/prepare-engraving/', views.prepare_engraving_api, name='prepare_engraving'),
    path('api/vectorize/', views.vectorize_image_api, name='vectorize_image'),
    
    # Erweiterte Funktionen
    path('api/advanced-filter/', views.apply_advanced_filter_api, name='apply_advanced_filter'),
    path('api/batch-process/', views.batch_process_api, name='batch_process'),
    path('api/live-preview/<int:project_id>/', views.get_live_preview_api, name='live_preview'),
    
    # Vorschau-APIs (ohne speichern)
    path('api/preview-filter/', views.preview_filter_api, name='preview_filter'),
    path('api/preview-remove-background/', views.preview_remove_background_api, name='preview_remove_background'),
    path('api/preview-prepare-engraving/', views.preview_prepare_engraving_api, name='preview_prepare_engraving'),
    path('api/preview-vectorize/', views.preview_vectorize_api, name='preview_vectorize'),
    
    # Canva Integration
    path('canva-import/', views.canva_import_view, name='canva_import'),
    path('api/canva-import-design/', views.canva_import_design_api, name='canva_import_design'),
    path('api/canva-designs/', views.canva_designs_api, name='canva_designs'),
    
    # Shopify Integration
    path('shopify-import/', views.shopify_import_view, name='shopify_import'),
    path('api/shopify-images/', views.shopify_images_api, name='shopify_images'),
    path('api/shopify-import-image/', views.shopify_import_image_api, name='shopify_import_image'),
    path('api/shopify-export-image/', views.shopify_export_image_api, name='shopify_export_image'),
    path('api/shopify-products/', views.shopify_products_api, name='shopify_products'),
    
    # Downloads
    path('download/<int:project_id>/<str:format>/', views.download_image_view, name='download_image'),
]
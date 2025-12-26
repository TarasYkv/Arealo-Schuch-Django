"""
BlogPrep URL Configuration

Wizard-basierte Blog-Erstellung in 7 Schritten
"""

from django.urls import path
from . import views

app_name = 'blogprep'

urlpatterns = [
    # Dashboard & Projekt-Liste
    path('', views.project_list, name='project_list'),
    path('project/<uuid:project_id>/delete/', views.project_delete, name='project_delete'),
    path('project/<uuid:project_id>/result/', views.project_result, name='project_result'),

    # Settings
    path('settings/', views.settings_view, name='settings'),
    path('api/scrape-products/', views.api_scrape_product_links, name='api_scrape_products'),

    # Wizard Step 1: Keywords
    path('wizard/step1/', views.wizard_step1, name='wizard_step1'),
    path('wizard/step1/<uuid:project_id>/', views.wizard_step1, name='wizard_step1_edit'),
    path('api/suggest-keywords/', views.api_suggest_keywords, name='api_suggest_keywords'),
    path('api/check-duplicate-keyword/', views.api_check_duplicate_keyword, name='api_check_duplicate_keyword'),

    # Wizard Step 2: Recherche & Gliederung
    path('wizard/step2/<uuid:project_id>/', views.wizard_step2, name='wizard_step2'),
    path('api/research/<uuid:project_id>/', views.api_run_research, name='api_run_research'),
    path('api/outline/<uuid:project_id>/', views.api_generate_outline, name='api_generate_outline'),

    # Wizard Step 3: Content
    path('wizard/step3/<uuid:project_id>/', views.wizard_step3, name='wizard_step3'),
    path('api/content/<uuid:project_id>/', views.api_generate_content_section, name='api_generate_content'),
    path('api/faqs/<uuid:project_id>/', views.api_generate_faqs, name='api_generate_faqs'),
    path('api/seo-meta/<uuid:project_id>/', views.api_generate_seo_meta, name='api_generate_seo_meta'),

    # Wizard Step 4: Bilder
    path('wizard/step4/<uuid:project_id>/', views.wizard_step4, name='wizard_step4'),
    path('api/title-image/<uuid:project_id>/', views.api_generate_title_image, name='api_generate_title_image'),
    path('api/section-image/<uuid:project_id>/', views.api_generate_section_image, name='api_generate_section_image'),
    path('api/suggest-section-images/<uuid:project_id>/', views.api_suggest_section_images, name='api_suggest_section_images'),
    path('api/server-images/<uuid:project_id>/', views.api_get_server_images, name='api_get_server_images'),
    path('api/use-server-image/<uuid:project_id>/', views.api_use_server_image, name='api_use_server_image'),
    path('api/delete-section-image/<uuid:project_id>/', views.api_delete_section_image, name='api_delete_section_image'),

    # Wizard Step 5: Diagramm
    path('wizard/step5/<uuid:project_id>/', views.wizard_step5, name='wizard_step5'),
    path('api/diagram-analyze/<uuid:project_id>/', views.api_analyze_for_diagram, name='api_analyze_diagram'),
    path('api/diagram-image/<uuid:project_id>/', views.api_generate_diagram_image, name='api_generate_diagram_image'),
    path('api/diagram-delete/<uuid:project_id>/', views.api_delete_diagram_image, name='api_delete_diagram_image'),

    # Wizard Step 6: Video-Skript
    path('wizard/step6/<uuid:project_id>/', views.wizard_step6, name='wizard_step6'),
    path('api/video-script/<uuid:project_id>/', views.api_generate_video_script, name='api_generate_video_script'),

    # Wizard Step 7: Export
    path('wizard/step7/<uuid:project_id>/', views.wizard_step7, name='wizard_step7'),
    path('api/export/<uuid:project_id>/', views.api_export_to_shopify, name='api_export_to_shopify'),
    path('api/blogs/<int:store_id>/', views.api_get_blogs_for_store, name='api_get_blogs'),
]

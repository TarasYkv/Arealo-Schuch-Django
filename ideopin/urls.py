from django.urls import path
from . import views

app_name = 'ideopin'

urlpatterns = [
    # Wizard-Schritte
    path('', views.wizard_step1, name='wizard_step1'),
    path('step1/', views.wizard_step1, name='wizard_step1_new'),
    path('step1/<int:project_id>/', views.wizard_step1, name='wizard_step1_edit'),
    path('step2/<int:project_id>/', views.wizard_step2, name='wizard_step2'),
    path('step3/<int:project_id>/', views.wizard_step3, name='wizard_step3'),
    path('step4/<int:project_id>/', views.wizard_step4, name='wizard_step4'),
    path('step5/<int:project_id>/', views.wizard_step5, name='wizard_step5'),
    path('result/<int:project_id>/', views.wizard_result, name='wizard_result'),

    # API-Endpunkte
    path('api/generate-keywords/', views.api_generate_keywords, name='api_generate_keywords'),
    path('api/keyword-history/', views.api_get_keyword_history, name='api_keyword_history'),
    path('api/link-history/', views.api_get_link_history, name='api_link_history'),
    path('api/product-image-history/', views.api_get_product_image_history, name='api_product_image_history'),
    path('api/set-product-image/<int:project_id>/', views.api_set_product_image_from_history, name='api_set_product_image'),
    path('api/generate-text/<int:project_id>/', views.api_generate_overlay_text, name='api_generate_text'),
    path('api/generate-styling/<int:project_id>/', views.api_generate_styling, name='api_generate_styling'),
    path('api/generate-background/<int:project_id>/', views.api_generate_background_description, name='api_generate_background'),
    path('api/generate-image/<int:project_id>/', views.api_generate_image, name='api_generate_image'),
    path('api/generate-variants/<int:project_id>/', views.api_generate_image_variants, name='api_generate_variants'),
    path('api/select-variant/<int:project_id>/', views.api_select_variant, name='api_select_variant'),
    path('api/apply-overlay/<int:project_id>/', views.api_apply_text_overlay, name='api_apply_overlay'),
    path('api/generate-title/<int:project_id>/', views.api_generate_pin_title, name='api_generate_title'),
    path('api/generate-seo/<int:project_id>/', views.api_generate_seo_description, name='api_generate_seo'),
    path('api/save-step3/<int:project_id>/', views.api_save_step3, name='api_save_step3'),
    path('api/upload-custom-image/<int:project_id>/', views.api_upload_custom_image, name='api_upload_custom_image'),

    # Management
    path('projects/', views.project_list, name='project_list'),
    path('delete/<int:project_id>/', views.project_delete, name='project_delete'),
    path('duplicate/<int:project_id>/', views.project_duplicate, name='project_duplicate'),
    path('download/<int:project_id>/', views.download_image, name='download_image'),
    path('settings/', views.settings_view, name='settings'),

    # Pinterest API
    path('api/pinterest/boards/', views.api_pinterest_boards, name='api_pinterest_boards'),
    path('api/pinterest/post/<int:project_id>/', views.api_post_to_pinterest, name='api_post_to_pinterest'),
    path('api/pinterest/mark-posted/<int:project_id>/', views.api_mark_as_posted, name='api_mark_as_posted'),
    path('api/pinterest/unmark-posted/<int:project_id>/', views.api_unmark_as_posted, name='api_unmark_as_posted'),
]

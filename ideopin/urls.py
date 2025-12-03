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
    path('api/generate-text/<int:project_id>/', views.api_generate_overlay_text, name='api_generate_text'),
    path('api/generate-styling/<int:project_id>/', views.api_generate_styling, name='api_generate_styling'),
    path('api/generate-image/<int:project_id>/', views.api_generate_image, name='api_generate_image'),
    path('api/apply-overlay/<int:project_id>/', views.api_apply_text_overlay, name='api_apply_overlay'),
    path('api/generate-seo/<int:project_id>/', views.api_generate_seo_description, name='api_generate_seo'),
    path('api/save-step3/<int:project_id>/', views.api_save_step3, name='api_save_step3'),

    # Management
    path('projects/', views.project_list, name='project_list'),
    path('delete/<int:project_id>/', views.project_delete, name='project_delete'),
    path('duplicate/<int:project_id>/', views.project_duplicate, name='project_duplicate'),
    path('download/<int:project_id>/', views.download_image, name='download_image'),
    path('settings/', views.settings_view, name='settings'),
]

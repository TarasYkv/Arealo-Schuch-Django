# amortization_calculator/urls.py

from django.urls import path
from . import views

app_name = 'amortization_calculator'

urlpatterns = [
    # Wizard Schritte
    path('start/', views.rechner_start_view, name='rechner_start'),
    path('wizard/step1/', views.wizard_step1, name='wizard_step1'),
    path('wizard/step1/<int:calc_id>/', views.wizard_step1, name='wizard_step1_edit'),
    path('wizard/step2/<int:calc_id>/', views.wizard_step2, name='wizard_step2'),
    path('wizard/step3/<int:calc_id>/', views.wizard_step3, name='wizard_step3'),
    path('wizard/step4/<int:calc_id>/', views.wizard_step4, name='wizard_step4'),
    path('wizard/results/<int:calc_id>/', views.wizard_results, name='wizard_results'),

    # Verwaltung
    path('list/', views.calculation_list, name='calculation_list'),
    path('delete/<int:calc_id>/', views.calculation_delete, name='calculation_delete'),
    path('duplicate/<int:calc_id>/', views.calculation_duplicate, name='calculation_duplicate'),
    path('export/<int:calc_id>/pdf/', views.export_pdf, name='export_pdf'),
    path('export/<int:calc_id>/pdf-details/', views.export_detailed_pdf, name='export_detailed_pdf'),

    # API Endpunkte
    path('api/validate/', views.api_validate, name='api_validate'),
]

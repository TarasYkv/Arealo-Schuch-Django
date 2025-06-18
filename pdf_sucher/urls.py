# VOLLSTÄNDIGER CODE FÜR: pdf_sucher/urls.py

from django.urls import path
from . import views

app_name = 'pdf_sucher'

urlpatterns = [
    path('suche/', views.pdf_suche, name='pdf_suche'),

    # KORREKTUR: Das überflüssige '/page/' wurde aus dem Pfad entfernt,
    # damit es zum Aufruf im Template passt.
    path('preview/<str:filename>/<int:page_num>/', views.pdf_page_preview, name='pdf_page_preview'),

    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),
    
    # Neue Endpoints für Ampel-Funktionalität
    path('ampel-locations/', views.get_ampel_locations, name='ampel_locations'),
    path('page-image/<str:filename>/<int:page_num>/', views.get_pdf_page_image, name='pdf_page_image'),
]
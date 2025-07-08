# PDF SUCHER & ZUSAMMENFASSUNG - URLS

from django.urls import path
from . import views

app_name = 'pdf_sucher'

urlpatterns = [
    # Bestehende PDF-Suche
    path('suche/', views.pdf_suche, name='pdf_suche'),
    path('preview/<str:filename>/<int:page_num>/', views.pdf_page_preview, name='pdf_page_preview'),
    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),
    path('ampel-locations/', views.get_ampel_locations, name='ampel_locations'),
    path('page-image/<str:filename>/<int:page_num>/', views.get_pdf_page_image, name='pdf_page_image'),
    
    # Neue PDF-Zusammenfassungsfunktionalität
    path('', views.document_list_view, name='document_list'),
    path('dokumente/', views.document_list_view, name='documents'),
    path('upload/', views.document_upload_view, name='document_upload'),
    path('dokument/<int:pk>/', views.document_detail_view, name='document_detail'),
    path('dokument/<int:pk>/loeschen/', views.delete_document_view, name='delete_document'),
    
    # Zusammenfassungen
    path('zusammenfassungen/', views.summary_list_view, name='summary_list'),
    path('dokument/<int:document_id>/zusammenfassung/erstellen/', views.create_summary_view, name='create_summary'),
    path('zusammenfassung/<int:pk>/', views.summary_detail_view, name='summary_detail'),
    path('zusammenfassung/<int:pk>/loeschen/', views.delete_summary_view, name='delete_summary'),
    path('zusammenfassung/<int:pk>/pdf-download/', views.download_summary_pdf_view, name='download_summary_pdf'),
    path('zusammenfassung/<int:pk>/pdf-regenerieren/', views.regenerate_summary_pdf_view, name='regenerate_summary_pdf'),
    
    # API Endpoints
    path('api/zusammenfassung/<int:pk>/status/', views.summary_status_api_view, name='summary_status_api'),
]
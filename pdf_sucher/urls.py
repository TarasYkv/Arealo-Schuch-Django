# Kompletter Inhalt für: pdf_sucher/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Dieser Pfad führt zur Hauptseite der App
    path('suche/', views.pdf_suche, name='pdf_suche'),

    # Dieser Pfad wird aufgerufen, um die gesamte PDF in einem neuen Tab anzuzeigen
    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),

    # KORREKTUR: Dieser fehlende Pfad wird hinzugefügt.
    # Er wird vom JavaScript aufgerufen, um das Bild für die Seitenvorschau zu laden.
    path('preview/<str:filename>/page/<int:page_num>/', views.pdf_page_preview, name='pdf_page_preview'),
]

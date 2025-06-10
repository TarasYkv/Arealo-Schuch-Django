# Kompletter Inhalt für: pdf_sucher/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Dieser Pfad führt zur Hauptseite der App
    path('suche/', views.pdf_suche, name='pdf_suche'),

    # KORREKTUR: Dieser fehlende Pfad wird hinzugefügt.
    # Er wird aufgerufen, um eine gespeicherte PDF anzuzeigen.
    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),
]

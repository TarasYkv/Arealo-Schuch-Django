# Kompletter Inhalt für: pdf_sucher/urls.py (NEUE DATEI)

from django.urls import path
from . import views

urlpatterns = [
    path('suche/', views.pdf_suche, name='pdf_suche'),
]

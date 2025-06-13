# Kompletter, finaler Inhalt für: sportplatzApp/urls.py

from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # NEUE Homepage
    path('', TemplateView.as_view(template_name='index.html'), name='homepage'),

    # URL für Schritt 1: Das Formular zur Bestandsaufnahme
    path('projekt/neu/', views.projekt_anlegen, name='projekt_anlegen'),

    # URL für die Ergebnisseite nach erfolgreicher Auswahl
    path('projekt/<int:projekt_id>/danke/', views.danke_seite, name='danke_seite'),

    # URL für den Fall, dass keine passende Variante gefunden wurde
    path('keine-variante/', views.keine_variante_gefunden, name='keine_variante_gefunden'),
]
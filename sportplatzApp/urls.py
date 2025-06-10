# sportplatzApp/urls.py

from django.urls import path
from . import views

# NEU: Dies registriert den Namespace 'sportplatzApp'
app_name = 'sportplatzApp'

urlpatterns = [
    # URL für den Startpunkt des Sportplatz-Konfigurators
    path('', views.sportplatz_start_view, name='sportplatz_start'),

    # URL für Schritt 1: Das Formular zur Bestandsaufnahme
    path('projekt/neu/', views.projekt_anlegen, name='projekt_anlegen'),

    # URL für die Ergebnisseite nach erfolgreicher Auswahl
    path('projekt/<int:projekt_id>/danke/', views.danke_seite, name='danke_seite'),

    # URL für den Fall, dass keine passende Variante gefunden wurde
    path('keine-variante/', views.keine_variante_gefunden, name='keine_variante_gefunden'),
]
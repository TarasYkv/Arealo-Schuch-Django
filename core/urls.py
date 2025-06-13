from django.contrib import admin
from django.urls import path, include

# Die View für die Startseite aus der 'core'-App importieren
from core import views as core_views

urlpatterns = [
    # Die Startseite liegt auf der Haupt-URL
    path('', core_views.startseite_ansicht, name='startseite'),

    # Der Admin-Bereich
    path('admin/', admin.site.urls),

    # --- Alle Apps sind jetzt korrekt mit ihrem eigenen Präfix eingebunden ---
    path('pdf-tool/', include('pdf_sucher.urls')),
    path('rechner/', include('amortization_calculator.urls')),
    path('sportplatz/', include('sportplatzApp.urls')),
]
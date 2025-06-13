# amortization_calculator/urls.py
# (Diese Datei wird von Ihrer Haupt-Schuch/urls.py mit include() verwendet)

from django.urls import path
from . import views # Dies importiert die Views aus amortization_calculator/views.py

# Optional, aber empfohlen für Namespaces (falls Sie es später verwenden möchten)
# app_name = 'amortization_calculator'

urlpatterns = [
    # DIESE ZEILE IST KRITISCH, damit 'rechner_start' gefunden wird
    path('start/', views.rechner_start_view, name='rechner_start'),
    # Fügen Sie hier weitere URL-Muster hinzu, die spezifisch für die Rechner-App sind
    # z.B. path('ergebnis/', views.rechner_ergebnis_view, name='rechner_ergebnis'),
]
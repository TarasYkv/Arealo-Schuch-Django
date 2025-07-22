# amortization_calculator/views.py

from django.shortcuts import render
from accounts.decorators import require_app_permission

@require_app_permission('wirtschaftlichkeitsrechner')
def rechner_start_view(request):
    """
    Rendert die Startseite des Wirtschaftlichkeitsrechners.
    Diese View wird aufgerufen, wenn die URL mit dem Namen 'rechner_start'
    aufgerufen wird (z.B. über {% url 'rechner_start' %} in einem Template).
    """

    # Hier können Sie Logik für den Rechner hinzufügen,
    # z.B. das Initialisieren von Formularen oder das Bereitstellen von Standardwerten.

    context = {
        'page_title': 'Wirtschaftlichkeitsrechner',
        # Fügen Sie hier weitere Daten hinzu, die Sie an das Template übergeben möchten
    }

    # WICHTIG: Das Template wird jetzt korrekt als 'rechner_formular.html' gerendert.
    return render(request, 'amortization_calculator/rechner_formular.html', context)


# Beispiel für eine weitere View, falls Sie weitere Seiten im Rechner haben
@require_app_permission('wirtschaftlichkeitsrechner')
def rechner_ergebnis_view(request):
    """
    Rendert die Ergebnisseite des Wirtschaftlichkeitsrechners.
    """
    if request.method == 'POST':
        # Verarbeiten Sie hier die Formulardaten vom Rechner
        # und berechnen Sie die Ergebnisse
        pass # Hier müsste Ihre Logik für die Ergebnisberechnung stehen

    context = {
        'page_title': 'Rechner-Ergebnisse',
        'ergebnis_daten': 'Ihre berechneten Daten hier',  # Beispiel-Platzhalter
    }

    # Rendert das Template für die Ergebnisseite
    return render(request, 'amortization_calculator/rechner_ergebnis.html', context)
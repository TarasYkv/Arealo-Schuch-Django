from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def lighting_tools_overview(request):
    """
    Overview page for all lighting industry tools
    """
    # Define all available lighting tools with their details
    tools = [
        {
            'name': 'Wirtschaftlichkeitsrechner',
            'url': 'amortization_calculator:rechner_start',
            'icon': 'bi-calculator',
            'color': 'primary',
            'description': 'Berechnen Sie die Wirtschaftlichkeit Ihrer LED-Umrüstung und ermitteln Sie ROI sowie Amortisationszeit.',
            'features': ['ROI-Berechnung', 'Energieeinsparungen', 'Wartungskosten', 'PDF-Export'],
            'permission': 'wirtschaftlichkeitsrechner',
            'status': 'available',
            'status_text': 'Verfügbar'
        },
        {
            'name': 'Beleuchtungsrechner',
            'url': 'beleuchtungsrechner',
            'icon': 'bi-lightbulb',
            'color': 'warning',
            'description': 'Professionelle Beleuchtungsplanung mit DIALux-Integration und 3D-Visualisierung.',
            'features': ['DIALux-Integration', '3D-Visualisierung', 'Lichtberechnung', 'Leuchten-Datenbank'],
            'permission': 'beleuchtungsrechner',
            'status': 'development',
            'status_text': 'In Entwicklung'
        },
        {
            'name': 'DIN 13201-1:2021-09 Klassifizierung',
            'url': 'lighting_classification:select_road_type',
            'icon': 'fas fa-road',
            'color': 'success',
            'description': 'Straßenbeleuchtung nach aktueller DIN-Norm klassifizieren und planen.',
            'features': ['Normgerechte Planung', 'Straßentypen', 'Beleuchtungsklassen', 'Compliance'],
            'permission': None,  # Always available
            'status': 'available',
            'status_text': 'Verfügbar'
        },
        {
            'name': 'Sportplatz-Konfigurator',
            'url': 'sportplatzApp:sportplatz_start',
            'icon': 'bi-geo-alt',
            'color': 'info',
            'description': 'Konfigurieren Sie die optimale Beleuchtung für verschiedene Sportanlagen.',
            'features': ['Sportarten-spezifisch', 'Normen-konform', 'Mastpositionierung', 'Lux-Berechnung'],
            'permission': 'sportplatz_konfigurator',
            'status': 'beta',
            'status_text': 'Beta'
        },
        {
            'name': 'PDF-Suche',
            'url': 'pdf_sucher:pdf_suche',
            'icon': 'bi-file-earmark-text',
            'color': 'secondary',
            'description': 'Durchsuchen Sie Produktkataloge und technische Dokumentationen intelligent.',
            'features': ['Volltextsuche', 'OCR-Erkennung', 'Katalog-Durchsuchung', 'Schnelle Ergebnisse'],
            'permission': 'pdf_suche',
            'status': 'available',
            'status_text': 'Verfügbar'
        },
        {
            'name': 'KI-Zusammenfassung',
            'url': 'pdf_sucher:document_list',
            'icon': 'bi-robot',
            'color': 'danger',
            'description': 'Automatische Zusammenfassung von technischen Dokumenten mit KI-Unterstützung.',
            'features': ['KI-Analyse', 'Zusammenfassungen', 'Dokumenten-Chat', 'Intelligente Suche'],
            'permission': 'ki_zusammenfassung',
            'status': 'development',
            'status_text': 'In Entwicklung'
        }
    ]

    context = {
        'tools': tools,
        'page_title': 'Beleuchtungs-Tools'
    }

    return render(request, 'lighting_tools/overview.html', context)

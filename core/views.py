# core/views.py
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from accounts.models import CustomPage, EditableContent

def startseite_ansicht(request):
    """Diese Ansicht rendert nur die Kachel-Übersicht."""
    context = {
        'current_page': 'startseite'
    }
    return render(request, 'core/startseite.html', context)

def dynamic_page_view(request, page_name):
    """Rendert dynamische benutzerdefinierte Seiten und System-Seiten"""
    if not request.user.is_authenticated:
        raise Http404("Seite nicht verfügbar")
    
    # Zuerst prüfen ob es eine benutzerdefinierte Seite ist
    try:
        page = CustomPage.objects.get(user=request.user, page_name=page_name, is_active=True)
        context = {
            'current_page': page_name,
            'page_title': page.display_name,
            'page_description': page.description,
        }
        return render(request, 'core/dynamic_page.html', context)
    except CustomPage.DoesNotExist:
        pass
    
    # Dann prüfen ob es eine System-Seite ist
    system_pages = _get_system_page_info(page_name)
    if system_pages:
        context = {
            'current_page': page_name,
            'page_title': system_pages['title'],
            'page_description': system_pages.get('description', ''),
            'is_system_page': True,
            'page_type': system_pages.get('type', 'generic')
        }
        return render(request, 'core/dynamic_page.html', context)
    
    raise Http404("Seite nicht gefunden")


def _get_system_page_info(page_name):
    """Gibt Informationen über System-Seiten zurück"""
    system_pages = {
        # App Dashboards
        'accounts_dashboard': {'title': 'Account Dashboard', 'type': 'dashboard', 'description': 'Verwalten Sie Ihre Kontoeinstellungen'},
        'mail_dashboard': {'title': 'Mail Dashboard', 'type': 'dashboard', 'description': 'E-Mail-Verwaltung und -Einstellungen'},
        'shopify_dashboard': {'title': 'Shopify Dashboard', 'type': 'dashboard', 'description': 'Shopify Store Management'},
        'image_editor_dashboard': {'title': 'Bild-Editor Dashboard', 'type': 'dashboard', 'description': 'Bildbearbeitung und -verwaltung'},
        'organization_dashboard': {'title': 'Organisation Dashboard', 'type': 'dashboard', 'description': 'Termine und Aufgaben verwalten'},
        'naturmacher_dashboard': {'title': 'Schulungen Dashboard', 'type': 'dashboard', 'description': 'Kurse und Lernmaterialien'},
        'videos_dashboard': {'title': 'Videos Dashboard', 'type': 'dashboard', 'description': 'Video-Verwaltung und -Hosting'},
        'chat_dashboard': {'title': 'Chat Dashboard', 'type': 'dashboard', 'description': 'Kommunikation und Nachrichten'},
        'somi_plan_dashboard': {'title': 'SOMI Plan Dashboard', 'type': 'dashboard', 'description': 'SOMI Planungstool'},
        'email_templates_dashboard': {'title': 'E-Mail Templates Dashboard', 'type': 'dashboard', 'description': 'E-Mail-Vorlagen verwalten'},
        
        # Landing Pages
        'landing_about': {'title': 'Über uns', 'type': 'landing', 'description': 'Erfahren Sie mehr über unser Unternehmen'},
        'landing_services': {'title': 'Services', 'type': 'landing', 'description': 'Unsere Dienstleistungen im Überblick'},
        'landing_pricing': {'title': 'Preise', 'type': 'landing', 'description': 'Unsere Preismodelle und Pakete'},
        'landing_contact': {'title': 'Kontakt', 'type': 'landing', 'description': 'Nehmen Sie Kontakt mit uns auf'},
        'landing_features': {'title': 'Features', 'type': 'landing', 'description': 'Alle Funktionen im Detail'},
        'landing_testimonials': {'title': 'Kundenstimmen', 'type': 'landing', 'description': 'Was unsere Kunden sagen'},
        'landing_blog': {'title': 'Blog', 'type': 'landing', 'description': 'Neuigkeiten und Artikel'},
        'landing_faq': {'title': 'FAQ', 'type': 'landing', 'description': 'Häufig gestellte Fragen'},
        
        # Shop Seiten
        'shop_products': {'title': 'Produkte', 'type': 'shop', 'description': 'Alle Produkte in unserem Shop'},
        'shop_categories': {'title': 'Kategorien', 'type': 'shop', 'description': 'Produktkategorien durchsuchen'},
        'shop_cart': {'title': 'Warenkorb', 'type': 'shop', 'description': 'Ihr Warenkorb'},
        'shop_checkout': {'title': 'Checkout', 'type': 'shop', 'description': 'Bestellung abschließen'},
        'shop_account': {'title': 'Kundenkonto', 'type': 'shop', 'description': 'Ihr Kundenkonto verwalten'},
        'shop_orders': {'title': 'Bestellungen', 'type': 'shop', 'description': 'Ihre Bestellübersicht'},
        
        # Funktionale Seiten
        'search_results': {'title': 'Suchergebnisse', 'type': 'functional', 'description': 'Suchergebnisse anzeigen'},
        'error_404': {'title': '404 - Seite nicht gefunden', 'type': 'error', 'description': 'Die angeforderte Seite wurde nicht gefunden'},
        'error_500': {'title': '500 - Serverfehler', 'type': 'error', 'description': 'Ein Serverfehler ist aufgetreten'},
        'maintenance': {'title': 'Wartungsarbeiten', 'type': 'functional', 'description': 'Website ist vorübergehend nicht verfügbar'},
        'coming_soon': {'title': 'Bald verfügbar', 'type': 'functional', 'description': 'Diese Funktion wird bald verfügbar sein'},
        
        # Global
        'header': {'title': 'Header Bereich', 'type': 'global', 'description': 'Globaler Header-Bereich'},
        'footer': {'title': 'Footer Bereich', 'type': 'global', 'description': 'Globaler Footer-Bereich'},
    }
    
    return system_pages.get(page_name)

def impressum_view(request):
    """Impressum Seite"""
    context = {
        'page_title': 'Impressum',
    }
    return render(request, 'core/impressum.html', context)

def agb_view(request):
    """AGB Seite"""
    context = {
        'page_title': 'Allgemeine Geschäftsbedingungen',
    }
    return render(request, 'core/agb.html', context)

def datenschutz_view(request):
    """Datenschutzbedingungen Seite"""
    context = {
        'page_title': 'Datenschutzerklärung',
    }
    return render(request, 'core/datenschutz.html', context)


def public_app_info(request, app_name):
    """Öffentliche App-Info-Seiten für nicht angemeldete Benutzer"""
    apps_info = {
        'todos': {
            'name': 'ToDo Manager Pro',
            'icon': 'bi-list-check',
            'color': 'primary',
            'short_desc': 'Die ultimative Aufgabenverwaltung für moderne Teams',
            'features': [
                'Intelligente Aufgabenplanung mit KI-Unterstützung',
                'Kollaborative Team-Workspaces mit Echtzeit-Synchronisation',
                'Erweiterte Prioritätssysteme und automatische Deadline-Erinnerungen',
                'Detaillierte Fortschrittsanalysen und Produktivitäts-Insights',
                'Integrierte Zeiterfassung und Projektbudget-Tracking',
                'Anpassbare Dashboards und mobile Apps für iOS/Android'
            ],
            'benefits': {
                'Maximale Produktivität': 'Steigern Sie Ihre Teameffizienz um durchschnittlich 65% durch intelligente Automatisierung',
                'Perfekte Organisation': 'Nie wieder verlorene Aufgaben - behalten Sie alle Projekte und Deadlines im Überblick',
                'Nahtlose Teamwork': 'Revolutionäre Kollaboration mit Echtzeit-Updates und integrierter Kommunikation',
                'Vollste Flexibilität': 'Komplett anpassbar an Ihre Arbeitsweise mit über 50 Integrationen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'organization': {
            'name': 'WorkSpace Elite',
            'icon': 'bi-building',
            'color': 'success',
            'short_desc': 'Ihr All-in-One Business Hub für maximale Produktivität',
            'features': [
                'KI-powered Terminplanung mit automatischer Konfliktauflösung',
                'Enterprise-Dokumentenmanagement mit Versionskontrolle',
                'Interaktive Mindmaps und digitale Whiteboards für Brainstorming',
                'Integrierte 4K-Videokonferenzen mit Bildschirmfreigabe',
                'Fortgeschrittene Teamanalytics und Performance-Dashboards',
                'Cross-Platform Synchronisation und Offline-Modus'
            ],
            'benefits': {
                'Revolutionäre Effizienz': 'Reduzieren Sie administrative Aufgaben um bis zu 70% durch intelligente Automatisierung',
                'Zentrale Kommandozentrale': 'Verwalten Sie alle Geschäftsprozesse von einer einzigen, intuitiven Plattform',
                'Grenzenlose Mobilität': 'Arbeiten Sie produktiv von überall - Cloud-basiert mit 99.9% Uptime-Garantie',
                'Intelligente Integration': 'Nahtlose Anbindung an über 100 Business-Tools und APIs'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'videos': {
            'name': 'VideoFlow Pro',
            'icon': 'bi-play-circle',
            'color': 'danger',
            'short_desc': 'Professionelles Video-Hosting der nächsten Generation',
            'features': [
                'Unbegrenzte 8K Video-Uploads mit intelligenter Komprimierung',
                'KI-basierte automatische Transkription in 50+ Sprachen',
                'Fortgeschrittene Video-SEO und Content-Discovery-Engine',
                'Interactive Video-Player mit Hotspots und Call-to-Actions',
                'Live-Streaming mit bis zu 100.000 gleichzeitigen Zuschauern',
                'Erweiterte Analytics und Zuschauerverhalten-Tracking'
            ],
            'benefits': {
                'Unlimited Skalierung': 'Bis zu 10TB Cloud-Speicher mit globaler CDN-Auslieferung',
                'Broadcast-Qualität': '8K Video-Unterstützung mit adaptiver Bitrate-Streaming',
                'Enterprise-Sicherheit': 'Ende-zu-Ende Verschlüsselung mit DRM-Schutz',
                'Tiefe Insights': 'Detaillierte Zuschaueranalytik mit Heatmaps und Engagement-Metriken'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'streamrec': {
            'name': 'StreamRec Studio Pro',
            'icon': 'bi-mic',
            'color': 'info',
            'short_desc': 'Die ultimative Content-Creation-Suite für Profis',
            'features': [
                '4K Bildschirmaufnahme mit Multi-Monitor-Unterstützung',
                'Professional-Grade Audio mit Rauschunterdrückung und EQ',
                'Multi-Stream Live-Broadcasting auf alle Plattformen gleichzeitig',
                'KI-gestützte automatische Nachbearbeitung und Schnitt',
                'Unbegrenztes Cloud-Backup mit intelligenter Archivierung',
                'Integrierte Grafik-Overlays und Green-Screen-Technologie'
            ],
            'benefits': {
                'Studio-Exzellenz': 'Broadcast-Qualität direkt vom Homeoffice mit professionellem Equipment-Sound',
                'Maximale Effizienz': 'Ein-Klick-Workflows für komplette Produktionen von Aufnahme bis Publishing',
                'Grenzenlose Kreativität': 'Perfekt für Podcasts, Webinare, Tutorials, Gaming-Streams und Corporate-Videos',
                'Absolute Sicherheit': 'Automatisches Cloud-Backup mit Versionierung und 30-Tage-Wiederherstellung'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'chat': {
            'name': 'ChatFlow Enterprise',
            'icon': 'bi-chat-dots',
            'color': 'warning',
            'short_desc': 'Next-Generation Business Communication Platform',
            'features': [
                'Intelligentes Echtzeit-Messaging mit KI-basierter Übersetzung',
                'Erweiterte Team-Workspaces mit themenbezogenen Kanälen',
                'Sichere Dateifreigabe bis 100GB mit Virus-Scanning',
                '4K Videoanrufe mit bis zu 500 Teilnehmern und Aufzeichnung',
                'Military-Grade Ende-zu-Ende Verschlüsselung mit Zero-Knowledge-Architektur',
                'Advanced Bot-Integration und Workflow-Automatisierung'
            ],
            'benefits': {
                'Instant-Produktivität': 'Blitzschnelle Kommunikation mit unter 50ms Latenz weltweit',
                'Absolute Sicherheit': 'DSGVO-konform mit deutschen Servern und höchsten Sicherheitsstandards',
                'Totale Integration': 'Nahtlose Anbindung an 200+ Business-Apps und Custom-APIs',
                'Endlose Skalierung': 'Unbegrenzte Nachrichtenspeicherung mit intelligenter Suchfunktion'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'shopify': {
            'name': 'ShopifyFlow AI',
            'icon': 'bi-shop',
            'color': 'secondary',
            'short_desc': 'KI-gestütztes E-Commerce Management für maximale Umsätze',
            'features': [
                'Intelligente Multi-Shop Verwaltung mit Unified Dashboard',
                'KI-basierte automatisierte Bestellabwicklung und Fulfillment',
                'Predictive Inventory Management mit Demand Forecasting',
                'Advanced Customer Analytics mit Lifetime Value Prediction',
                'Omnichannel Marketing-Automatisierung mit A/B Testing',
                'Dynamische Preisoptimierung und Conversion-Rate-Optimierung'
            ],
            'benefits': {
                'Umsatzexplosion': 'Steigern Sie Ihren Umsatz um durchschnittlich 85% durch KI-optimierte Prozesse',
                'Totale Automatisierung': 'Reduzieren Sie manuelle Aufgaben um bis zu 95% durch intelligente Workflows',
                'Kompletter Überblick': 'Verwalten Sie unbegrenzt viele Shops von einem zentralen Control-Center',
                'Unbegrenztes Wachstum': 'Skalieren Sie mühelos von Startup bis Enterprise mit elastischer Infrastruktur'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        }
    }
    
    app_data = apps_info.get(app_name)
    if not app_data:
        raise Http404("App nicht gefunden")
    
    # Get editable content if exists
    editable_content = {}
    if request.user.is_authenticated and request.user.is_superuser:
        editable_content = EditableContent.get_content_for_page(f'app_info_{app_name}')
    
    context = {
        'app_name': app_name,
        'app': app_data,
        'editable_content': editable_content,
        'is_public': True,
        'current_page': f'app_info_{app_name}'
    }
    
    return render(request, 'core/public_app_info.html', context)
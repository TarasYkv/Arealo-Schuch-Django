# core/views.py
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from accounts.models import CustomPage

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
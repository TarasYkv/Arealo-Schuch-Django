"""
Core page registry to centralize system page definitions and avoid duplication.

Provides helpers to fetch page info and choices for UI selectors.
"""

from typing import Dict, List, Tuple, Optional


# Central definition of system pages used across the app
SYSTEM_PAGES: Dict[str, Dict[str, str]] = {
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
    'fileshare_dashboard': {'title': 'Datei-Transfer Dashboard', 'type': 'dashboard', 'description': 'Dateien teilen und verwalten'},

    # Landing Pages
    'landing_about': {'title': 'Über uns', 'type': 'landing', 'description': 'Erfahren Sie mehr über unser Unternehmen'},
    'landing_services': {'title': 'Services', 'type': 'landing', 'description': 'Unsere Dienstleistungen im Überblick'},
    'landing_pricing': {'title': 'Preise', 'type': 'landing', 'description': 'Unsere Preismodelle und Pakete'},
    'landing_contact': {'title': 'Kontakt', 'type': 'landing', 'description': 'Nehmen Sie Kontakt mit uns auf'},
    'landing_features': {'title': 'Features', 'type': 'landing', 'description': 'Alle Funktionen im Detail'},
    'landing_testimonials': {'title': 'Kundenstimmen', 'type': 'landing', 'description': 'Was unsere Kunden sagen'},
    'landing_blog': {'title': 'Blog', 'type': 'landing', 'description': 'Neuigkeiten und Artikel'},
    'landing_faq': {'title': 'FAQ', 'type': 'landing', 'description': 'Häufig gestellte Fragen'},

    # Shop Pages
    'shop_products': {'title': 'Produkte', 'type': 'shop', 'description': 'Alle Produkte in unserem Shop'},
    'shop_categories': {'title': 'Kategorien', 'type': 'shop', 'description': 'Produktkategorien durchsuchen'},
    'shop_cart': {'title': 'Warenkorb', 'type': 'shop', 'description': 'Ihr Warenkorb'},
    'shop_checkout': {'title': 'Checkout', 'type': 'shop', 'description': 'Bestellung abschließen'},
    'shop_account': {'title': 'Kundenkonto', 'type': 'shop', 'description': 'Ihr Kundenkonto verwalten'},
    'shop_orders': {'title': 'Bestellungen', 'type': 'shop', 'description': 'Ihre Bestellübersicht'},

    # Functional Pages
    'search_results': {'title': 'Suchergebnisse', 'type': 'functional', 'description': 'Suchergebnisse anzeigen'},
    'error_404': {'title': '404 - Seite nicht gefunden', 'type': 'error', 'description': 'Die angeforderte Seite wurde nicht gefunden'},
    'error_500': {'title': '500 - Serverfehler', 'type': 'error', 'description': 'Ein Serverfehler ist aufgetreten'},
    'maintenance': {'title': 'Wartungsarbeiten', 'type': 'functional', 'description': 'Website ist vorübergehend nicht verfügbar'},
    'coming_soon': {'title': 'Bald verfügbar', 'type': 'functional', 'description': 'Diese Funktion wird bald verfügbar sein'},

    # Global
    'header': {'title': 'Header Bereich', 'type': 'global', 'description': 'Globaler Header-Bereich'},
    'footer': {'title': 'Footer Bereich', 'type': 'global', 'description': 'Globaler Footer-Bereich'},
}


def get_system_page_info(page_name: str) -> Optional[Dict[str, str]]:
    return SYSTEM_PAGES.get(page_name)


def get_system_page_choices() -> List[Tuple[str, str]]:
    """Return (value, label) choices for system pages with emojis grouped externally."""
    # Keep order logical: landing -> shop -> dashboards -> functional -> global
    order_keys = [
        'landing_about', 'landing_services', 'landing_pricing', 'landing_contact', 'landing_features',
        'landing_testimonials', 'landing_blog', 'landing_faq',
        'shop_products', 'shop_categories', 'shop_cart', 'shop_checkout', 'shop_account', 'shop_orders',
        'accounts_dashboard', 'mail_dashboard', 'shopify_dashboard', 'image_editor_dashboard', 'organization_dashboard',
        'naturmacher_dashboard', 'videos_dashboard', 'chat_dashboard', 'somi_plan_dashboard', 'email_templates_dashboard', 'fileshare_dashboard',
        'search_results', 'error_404', 'error_500', 'maintenance', 'coming_soon',
        'header', 'footer',
    ]

    choices: List[Tuple[str, str]] = []
    for key in order_keys:
        info = SYSTEM_PAGES.get(key)
        if not info:
            continue
        emoji = '📄'
        if info['type'] == 'dashboard':
            emoji = '🎛️'
        elif info['type'] == 'landing':
            emoji = '🌟'
        elif info['type'] == 'shop':
            emoji = '🛒'
        elif info['type'] == 'functional':
            emoji = '🔧'
        elif info['type'] == 'error':
            emoji = '❌'
        elif info['type'] == 'global':
            emoji = '🌐'

        choices.append((key, f"{emoji} {info['title']}"))
    return choices


def get_app_info_page_choices(user=None) -> List[Tuple[str, str]]:
    """Return editor choices for public app info pages, honoring frontend visibility if possible."""
    choices: List[Tuple[str, str]] = []
    try:
        from accounts.models import AppPermission, UserAppPermission
    except Exception:
        return choices

    # Build set of top-level app names from AppPermission.APP_CHOICES
    # Exclude obvious sub-features to keep list clean
    exclude_prefixes = (
        'shopify_', 'organisation_',
    )

    for app_name, display in AppPermission.APP_CHOICES:
        if any(app_name.startswith(prefix) for prefix in exclude_prefixes):
            continue
        # Skip internal non-public labels if needed
        # Editor itself should not have an app info page
        if app_name in ('editor', 'schuch_dashboard'):
            continue

        # Honor frontend visibility when a user is provided
        visible = True
        if user is not None:
            try:
                visible = UserAppPermission.user_can_see_app_in_frontend(app_name, user)
            except Exception:
                visible = True

        if visible:
            choices.append((f'app_info_{app_name}', f'ℹ️ App: {display}'))

    return choices

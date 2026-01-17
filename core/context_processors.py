# core/context_processors.py
"""
SEO Context Processor & Dynamic Menu
Stellt SEO-relevante Informationen und dynamisches Menü für alle Templates bereit
"""

from django.conf import settings
from django.urls import reverse, NoReverseMatch
import logging

logger = logging.getLogger(__name__)


# Menü-Struktur Definition
# Mapping von App-Namen zu Menü-Kategorien mit URLs
MENU_STRUCTURE = {
    'schuch': {
        'key': 'schuch',
        'label': 'Schuch',
        'icon': 'bi bi-building',
        'order': 5,
        'requires_app': 'schuch',  # Nur anzeigen wenn Schuch-App aktiviert
        'apps': [
            {
                'app_name': 'schuch_dashboard',
                'label': 'Schuch Dashboard',
                'icon': 'bi bi-speedometer2',
                'auth_url_name': 'organization:schuch_dashboard',
            },
            {'divider': True},
            {
                'app_name': 'wirtschaftlichkeitsrechner',
                'label': 'Wirtschaftlichkeitsrechner',
                'icon': 'bi bi-calculator',
                'auth_url_name': 'amortization_calculator:rechner_start',
            },
            {
                'app_name': 'beleuchtungsrechner',
                'label': 'Beleuchtungsrechner',
                'icon': 'bi bi-lightbulb',
                'auth_url_name': 'beleuchtungsrechner',
            },
            {
                'app_name': 'din_13201',
                'label': 'DIN 13201-1 Klassifizierung',
                'icon': 'fas fa-road',
                'auth_url_name': 'lighting_classification:select_road_type',
            },
            {
                'app_name': 'sportplatz_konfigurator',
                'label': 'Sportplatz-Konfigurator',
                'icon': 'bi bi-geo-alt',
                'auth_url_name': 'sportplatzApp:sportplatz_start',
            },
            {
                'app_name': 'pdf_suche',
                'label': 'PDF-Suche',
                'icon': 'bi bi-file-earmark-text',
                'auth_url_name': 'pdf_sucher:pdf_suche',
            },
            {
                'app_name': 'ki_zusammenfassung',
                'label': 'KI-Zusammenfassung',
                'icon': 'bi bi-robot',
                'auth_url_name': 'pdf_sucher:document_list',
            },
        ],
    },
    'seo': {
        'key': 'seo',
        'label': 'SEO',
        'icon': 'bi bi-search-heart',
        'order': 10,
        'apps': [
            {
                'app_name': 'seo_dashboard',
                'label': 'SEO Dashboard',
                'icon': 'bi bi-speedometer2',
                'auth_url_name': 'seo_dashboard',
                'is_header': True,
            },
            {'divider': True},
            {
                'app_name': 'loomline',
                'label': 'LoomLine',
                'icon': 'fas fa-list-alt',
                'auth_url_name': 'loomline:dashboard',
                'sub_items': [
                    {'label': 'Dashboard', 'icon': 'fas fa-tachometer-alt', 'url_name': 'loomline:dashboard'},
                    {'label': 'Projekte', 'icon': 'fas fa-project-diagram', 'url_name': 'loomline:project-list'},
                    {'label': 'Aufgaben-Übersicht', 'icon': 'fas fa-th', 'url_name': 'loomline:tasks-tiles'},
                    {'label': 'Neues eintragen', 'icon': 'fas fa-plus', 'url_name': 'loomline:quick-add-task'},
                ],
            },
            {'divider': True},
            {
                'app_name': 'keyengine',
                'label': 'KeyEngine',
                'icon': 'fas fa-key',
                'auth_url_name': 'keyengine:dashboard',
            },
            {'divider': True},
            {
                'app_name': 'questionfinder',
                'label': 'QuestionFinder',
                'icon': 'fas fa-question-circle',
                'auth_url_name': 'questionfinder:dashboard',
                'sub_items': [
                    {'label': 'Fragen suchen', 'icon': 'fas fa-search', 'url_name': 'questionfinder:dashboard'},
                    {'label': 'Gespeicherte Fragen', 'icon': 'fas fa-bookmark', 'url_name': 'questionfinder:saved_questions'},
                ],
            },
            {'divider': True},
            {
                'app_name': 'backloom',
                'label': 'BackLoom',
                'icon': 'fas fa-link',
                'auth_url_name': 'backloom:dashboard',
                'sub_items': [
                    {'label': 'Dashboard', 'icon': 'fas fa-tachometer-alt', 'url_name': 'backloom:dashboard'},
                    {'label': 'Feed', 'icon': 'fas fa-rss', 'url_name': 'backloom:feed'},
                    {'label': 'Suchhistorie', 'icon': 'fas fa-history', 'url_name': 'backloom:search_history'},
                ],
            },
        ],
    },
    'media': {
        'key': 'media',
        'label': 'Media',
        'icon': 'fas fa-play-circle',
        'order': 20,
        'apps': [
            {
                'app_name': 'schulungen',
                'label': 'Schulungen',
                'icon': 'fas fa-graduation-cap',
                'auth_url_name': 'naturmacher:thema_list',
            },
            {
                'app_name': 'bilder',
                'label': 'Bilder',
                'icon': 'fas fa-images',
                'auth_url_name': 'image_editor:dashboard',
            },
            {
                'app_name': 'videos',
                'label': 'Videos',
                'icon': 'fas fa-video',
                'auth_url_name': 'videos:list',
            },
            {
                'app_name': 'streamrec',
                'label': 'StreamRec',
                'icon': 'fas fa-video-camera',
                'auth_url_name': 'streamrec:dashboard',
            },
            {
                'app_name': 'promptpro',
                'label': 'PromptPro',
                'icon': 'bi bi-collection',
                'auth_url_name': 'promptpro:prompt_list',
            },
            {
                'app_name': 'myprompter',
                'label': 'MyPrompter',
                'icon': 'bi bi-mic-fill',
                'auth_url_name': 'myprompter:teleprompter',
            },
            {
                'app_name': 'fileshare',
                'label': 'FileShare',
                'icon': 'fas fa-share-alt',
                'auth_url_name': 'fileshare:index',
            },
        ],
    },
    'shopify': {
        'key': 'shopify',
        'label': 'Shopify',
        'icon': 'bi bi-shop',
        'order': 30,
        'requires_app': 'shopify',  # Hauptapp die aktiviert sein muss
        'apps': [
            {
                'app_name': 'shopify',
                'label': 'ShopifyFlow',
                'icon': 'bi bi-shop-window',
                'auth_url_name': 'shopify_manager:dashboard',
                'sub_items': [
                    {'label': 'Dashboard', 'icon': 'bi bi-speedometer2', 'url_name': 'shopify_manager:dashboard'},
                    {'label': 'Produkte', 'icon': 'bi bi-box-seam', 'url_name': 'shopify_manager:product_list'},
                    {'label': 'Kategorien', 'icon': 'bi bi-collection', 'url_name': 'shopify_manager:collection_list'},
                    {'label': 'Blogs', 'icon': 'bi bi-journal-text', 'url_name': 'shopify_manager:blog_list'},
                    {'label': 'Stores', 'icon': 'bi bi-shop-window', 'url_name': 'shopify_manager:store_list'},
                    {'label': 'Backups', 'icon': 'bi bi-cloud-download', 'url_name': 'shopify_manager:backup_overview'},
                ],
            },
            {
                'app_name': 'blogprep',
                'label': 'BlogPrep',
                'icon': 'bi bi-pencil-square',
                'auth_url_name': 'blogprep:project_list',
            },
        ],
    },
    'kreativ': {
        'key': 'kreativ',
        'label': 'Kreativ',
        'icon': 'bi bi-palette',
        'order': 40,
        'apps': [
            {
                'app_name': 'makeads',
                'label': 'AdsMake',
                'icon': 'bi bi-megaphone',
                'auth_url_name': 'makeads:dashboard',
            },
            {
                'app_name': 'somi_plan',
                'label': 'SoMi-Plan',
                'icon': 'bi bi-graph-up',
                'auth_url_name': 'somi_plan:dashboard',
            },
            {
                'app_name': 'ideopin',
                'label': 'IdeoPin',
                'icon': 'bi bi-pinterest text-danger',
                'auth_url_name': 'ideopin:wizard_step1',
            },
            {
                'app_name': 'imageforge',
                'label': 'ImageForge',
                'icon': 'bi bi-image text-primary',
                'auth_url_name': 'imageforge:dashboard',
            },
            {
                'app_name': 'vskript',
                'label': 'VSkript',
                'icon': 'bi bi-camera-video text-success',
                'auth_url_name': 'vskript:dashboard',
            },
        ],
    },
    'organisation': {
        'key': 'organisation',
        'label': 'Organisation',
        'icon': 'fas fa-building',
        'order': 50,
        'apps': [
            {
                'app_name': 'organisation',
                'label': 'WorkSpace',
                'icon': 'fas fa-clipboard-list',
                'auth_url_name': 'organization:dashboard',
                'sub_items': [
                    {'label': 'Organisation', 'icon': 'fas fa-clipboard-list', 'url_name': 'organization:dashboard'},
                    {'label': 'Notizen', 'icon': 'fas fa-sticky-note', 'url_name': 'organization:note_list'},
                    {'label': 'Ideenboards', 'icon': 'fas fa-lightbulb', 'url_name': 'organization:board_list'},
                    {'label': 'Termine', 'icon': 'fas fa-calendar-alt', 'url_name': 'organization:calendar_view'},
                ],
            },
            {
                'app_name': 'todos',
                'label': 'ToDos',
                'icon': 'fas fa-tasks',
                'auth_url_name': 'todos:home',
            },
            {'divider': True, 'label': 'Kommunikation'},
            {
                'app_name': 'chat',
                'label': 'Chat',
                'icon': 'bi bi-chat-text',
                'auth_url_name': 'organization:chat_home',
                'show_notification_badge': True,
            },
            {
                'app_name': 'mail',
                'label': 'Email',
                'icon': 'bi bi-envelope',
                'auth_url_name': 'mail_app:dashboard',
            },
            {
                'app_name': 'loomconnect',
                'label': 'LoomConnect',
                'icon': 'bi bi-people',
                'auth_url_name': 'loomconnect:dashboard',
            },
            {'divider': True, 'label': 'Profile'},
            {
                'app_name': 'linkloom',
                'label': 'LinkLoom',
                'icon': 'fas fa-link',
                'auth_url_name': 'linkloom:dashboard',
            },
            {'divider': True, 'label': 'Apps'},
            {
                'app_name': 'android_apk_manager',
                'label': 'APK Manager',
                'icon': 'bi bi-phone',
                'auth_url_name': 'android_apk_manager:dashboard',
            },
        ],
    },
}


# Cache für App-Permissions (wird pro Request befüllt)
_permissions_cache = {}
_individual_permissions_cache = {}
_selected_users_cache = {}


def _load_permissions_cache(user):
    """
    Lädt alle AppPermissions in einem Query und cached sie.
    Reduziert N+1 Queries auf 2-3 Queries total.
    """
    global _permissions_cache, _individual_permissions_cache, _selected_users_cache
    from accounts.models import AppPermission, UserAppPermission

    # Alle globalen Permissions in einem Query laden
    permissions = AppPermission.objects.filter(is_active=True).prefetch_related('selected_users')
    _permissions_cache = {p.app_name: p for p in permissions}

    # Individuelle Permissions laden (falls User eingeloggt)
    _individual_permissions_cache = {}
    if user and user.is_authenticated:
        individual_perms = UserAppPermission.objects.filter(user=user)
        for perm in individual_perms:
            _individual_permissions_cache[perm.app_name] = perm.override_type == 'allow'

    # Selected Users Cache vorbereiten
    _selected_users_cache = {}
    if user and user.is_authenticated:
        for app_name, permission in _permissions_cache.items():
            if permission.access_level == 'selected':
                # Prüfe ob User in selected_users ist (aus prefetched Daten)
                _selected_users_cache[app_name] = user.id in [u.id for u in permission.selected_users.all()]


def _clear_permissions_cache():
    """Cache leeren nach Request"""
    global _permissions_cache, _individual_permissions_cache, _selected_users_cache
    _permissions_cache = {}
    _individual_permissions_cache = {}
    _selected_users_cache = {}


def _get_app_visibility(app_name, user):
    """
    Prüft ob eine App für einen User im Menü sichtbar sein soll.
    Nutzt gecachte Permissions für bessere Performance.

    Returns:
        tuple: (is_visible, has_access) - is_visible für Menü-Anzeige, has_access für direkten Zugriff
    """
    try:
        # Prüfe individuelle Berechtigung aus Cache
        if app_name in _individual_permissions_cache:
            result = _individual_permissions_cache[app_name]
            return result, result

        # Prüfe globale AppPermission aus Cache
        permission = _permissions_cache.get(app_name)
        if not permission:
            # Keine Einstellung = für Superuser sichtbar, sonst nicht
            if user and user.is_authenticated and user.is_superuser:
                return True, True
            return False, False

        # Prüfe access_level
        access_level = permission.access_level

        # Superuser-Bypass: Wenn aktiviert, haben Superuser IMMER Zugriff (auch bei blocked)
        if user and user.is_authenticated and user.is_superuser and permission.superuser_bypass:
            return True, True

        # Gesperrt = nicht anzeigen (außer Superuser mit Bypass, s.o.)
        if access_level == 'blocked':
            return False, False

        # In Entwicklung = nur Superuser
        if access_level == 'in_development':
            if user and user.is_authenticated and user.is_superuser:
                return True, True
            return False, False

        # Hide in frontend prüfen
        if permission.hide_in_frontend:
            if user and user.is_authenticated and user.is_superuser:
                return True, True
            return False, False

        # Anonym = für alle im Menü sichtbar
        if access_level == 'anonymous':
            return True, True

        # Authentifiziert = für alle im Menü sichtbar, aber nur angemeldete haben Zugriff
        if access_level == 'authenticated':
            has_access = user and user.is_authenticated
            return True, has_access  # Im Menü immer sichtbar!

        # Ausgewählte Nutzer - aus Cache
        if access_level == 'selected':
            if user and user.is_authenticated:
                has_access = _selected_users_cache.get(app_name, False)
                return has_access, has_access
            return False, False

        return False, False

    except Exception as e:
        logger.error(f"Error checking app visibility for {app_name}: {e}")
        return False, False


def _resolve_url(url_name, is_public=False, app_name=None):
    """Löst URL-Namen auf und gibt Info-Seite für nicht-angemeldete zurück"""
    if is_public and app_name:
        try:
            return reverse('public_app_info', args=[app_name])
        except NoReverseMatch:
            return '#'

    try:
        return reverse(url_name)
    except NoReverseMatch:
        return '#'


def dynamic_menu(request):
    """
    Context Processor für das dynamische Menü.

    Liefert:
        dynamic_menu: Dict mit Menü-Kategorien und deren Apps
        - Jede Kategorie enthält: label, icon, visible, apps
        - Jede App enthält: label, icon, url, visible, has_access
    """
    user = getattr(request, 'user', None)
    is_authenticated = user and user.is_authenticated

    # Cache laden für diesen Request (reduziert ~60 Queries auf 2-3)
    _load_permissions_cache(user)

    menu_result = {}

    for category_key, category_def in MENU_STRUCTURE.items():
        # Prüfe ob Hauptapp erforderlich ist
        requires_app = category_def.get('requires_app')
        if requires_app:
            is_visible, _ = _get_app_visibility(requires_app, user)
            if not is_visible:
                continue

        category_apps = []
        category_has_visible_apps = False

        for app_def in category_def.get('apps', []):
            # Divider
            if app_def.get('divider'):
                category_apps.append({
                    'is_divider': True,
                    'label': app_def.get('label', ''),
                })
                continue

            app_name = app_def.get('app_name')
            if not app_name:
                continue

            # Sichtbarkeit prüfen
            is_visible, has_access = _get_app_visibility(app_name, user)

            if not is_visible:
                continue

            # URL bestimmen
            auth_url_name = app_def.get('auth_url_name', '')
            if is_authenticated and has_access:
                url = _resolve_url(auth_url_name)
            else:
                url = _resolve_url(None, is_public=True, app_name=app_name)

            # Sub-Items verarbeiten
            sub_items = []
            if app_def.get('sub_items') and is_authenticated and has_access:
                for sub in app_def['sub_items']:
                    sub_url = _resolve_url(sub.get('url_name', ''))
                    sub_items.append({
                        'label': sub.get('label', ''),
                        'icon': sub.get('icon', ''),
                        'url': sub_url,
                    })

            app_item = {
                'app_name': app_name,
                'label': app_def.get('label', app_name),
                'icon': app_def.get('icon', 'bi bi-app'),
                'url': url,
                'visible': True,
                'has_access': has_access,
                'is_header': app_def.get('is_header', False),
                'sub_items': sub_items,
                'show_notification_badge': app_def.get('show_notification_badge', False),
            }

            category_apps.append(app_item)
            category_has_visible_apps = True

        # Kategorie nur hinzufügen wenn sie sichtbare Apps hat
        if category_has_visible_apps:
            menu_result[category_key] = {
                'key': category_key,
                'label': category_def.get('label', category_key),
                'icon': category_def.get('icon', ''),
                'order': category_def.get('order', 99),
                'apps': category_apps,
                'visible': True,
            }

    # Nach Order sortieren
    sorted_menu = dict(sorted(menu_result.items(), key=lambda x: x[1].get('order', 99)))

    # Cache leeren nach Verarbeitung
    _clear_permissions_cache()

    return {
        'dynamic_menu': sorted_menu,
    }


def seo_defaults(request):
    """
    Fügt Standard-SEO-Informationen zum Template-Context hinzu
    """
    # Basis-URL für kanonische Links und Open Graph
    protocol = 'https' if request.is_secure() else 'http'
    current_url = f"{protocol}://{request.get_host()}{request.path}"

    # Default SEO-Werte (können in Templates überschrieben werden)
    seo_context = {
        'seo': {
            'site_name': 'WorkLoom',
            'site_domain': settings.SITE_DOMAIN,
            'site_protocol': getattr(settings, 'SITE_PROTOCOL', 'https'),
            'canonical_url': current_url,
            'default_title': 'WorkLoom - Digitale Tools für effizientes Arbeiten',
            'default_description': 'WorkLoom bietet professionelle digitale Tools und Lösungen für Beleuchtungsplanung, Projektmanagement und mehr. Effizient, sicher und benutzerfreundlich.',
            'default_keywords': 'WorkLoom, Beleuchtungsrechner, Projektmanagement, digitale Tools, Beleuchtungsplanung, DIN EN 13201',
            'default_image': f"{protocol}://{request.get_host()}/media/workloom_icon.png",
            'og_type': 'website',
            'twitter_card': 'summary_large_image',
            'twitter_site': '@workloom',  # Anpassen wenn vorhanden
            'language': 'de-DE',
            'robots': 'index, follow',
        }
    }

    return seo_context

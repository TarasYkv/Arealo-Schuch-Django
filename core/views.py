# core/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.models import CustomPage, EditableContent
from accounts.decorators import require_app_permission
from core.page_registry import get_system_page_info

@require_app_permission('beleuchtungsrechner')
def beleuchtungsrechner(request):
    """Beleuchtungsrechner Tool für Schuch"""
    return render(request, 'core/beleuchtungsrechner.html')

def startseite_ansicht(request):
    """Diese Ansicht rendert die Startseite mit verfügbaren Apps."""
    available_apps = _get_available_apps()

    context = {
        'current_page': 'startseite',
        'available_apps': available_apps
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
    system_pages = get_system_page_info(page_name)
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
    """Backward-compat wrapper (kept for safety)."""
    return get_system_page_info(page_name)

def impressum_view(request):
    """Impressum Seite"""
    context = {
        'page_title': 'Impressum',
        'current_page': 'impressum',
    }
    return render(request, 'core/impressum.html', context)

def agb_view(request):
    """AGB Seite"""
    context = {
        'page_title': 'Allgemeine Geschäftsbedingungen',
        'current_page': 'agb',
    }
    return render(request, 'core/agb.html', context)

def datenschutz_view(request):
    """Datenschutzbedingungen Seite"""
    context = {
        'page_title': 'Datenschutzerklärung',
        'current_page': 'datenschutz',
    }
    return render(request, 'core/datenschutz.html', context)


def _get_available_apps():
    """Gibt alle öffentlich sichtbaren Apps mit ihren Informationen zurück

    Zeigt Apps mit access_level 'authenticated' oder 'anonymous' an.
    Beide Benutzertypen sehen die gleichen Apps - nicht-angemeldete werden
    auf Info-Seiten weitergeleitet, angemeldete auf die echten Tools.
    """
    from accounts.models import AppPermission
    from django.db.models import Q

    # Alle öffentlich sichtbaren Apps laden (authenticated ODER anonymous)
    available_permissions = AppPermission.objects.filter(
        Q(access_level='authenticated') | Q(access_level='anonymous'),
        is_active=True,
        hide_in_frontend=False
    )
    
    # Alle App-Informationen (keys müssen mit AppPermission.app_name übereinstimmen)
    all_apps = {
        'todos': {
            'name': 'ToDo Manager',
            'icon': 'bi-list-check',
            'color': 'primary',
            'app_url': '/todos/',
            'short_desc': 'Einfache und effektive Aufgabenverwaltung für Teams',
            'features': [
                'To-Do-Listen erstellen und verwalten',
                'Aufgaben zwischen Teammitgliedern zuweisen',
                'Status-Updates und Kommentarfunktion',
                'Listen-basierte Organisation',
                'KI-Unterstützung (in Entwicklung)',
                'Team-Kollaboration (in Entwicklung)'
            ],
            'benefits': {
                'Einfache Organisation': 'Behalte alle Aufgaben und Projekte strukturiert im Überblick',
                'Team-Koordination': 'Weise Aufgaben zu und verfolge den Fortschritt',
                'Beta-Features': 'Neue Funktionen werden kontinuierlich entwickelt und getestet',
                'Benutzerfreundlich': 'Intuitive Bedienung ohne komplexe Einrichtung'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'organisation': {
            'name': 'WorkSpace',
            'icon': 'bi-building',
            'color': 'success',
            'app_url': '/organization/',
            'short_desc': 'Organisiere Termine, Notizen und Ideen zentral',
            'features': [
                'Notizen erstellen und verwalten',
                'Kalender mit Terminerstellung',
                'Digitale Ideenboards mit Kollaboration',
                'Video/Audio-Calls zwischen Nutzern',
                'KI-Terminplanung (in Entwicklung)'
            ],
            'benefits': {
                'Zentrale Organisation': 'Alle wichtigen Informationen und Termine an einem Ort',
                'Team-Kollaboration': 'Arbeite gemeinsam an Ideen und Projekten',
                'Integrierte Kommunikation': 'Direct Calls und Zusammenarbeit möglich',
                'Beta-Entwicklung': 'Ständig neue Features in der Entwicklungsphase'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'videos': {
            'name': 'VideoFlow',
            'icon': 'bi-play-circle',
            'color': 'danger',
            'app_url': '/videos/',
            'short_desc': 'Einfaches Video-Hosting und -Management',
            'features': [
                'Video-Upload und -Speicherung',
                'Öffentliche und private Video-Links',
                'Embed-Player für Websites',
                'Video-Archivierung und Prioritäten',
                'Storage-Management',
                'KI-Transkription (in Entwicklung)'
            ],
            'benefits': {
                'Sicheres Hosting': 'Deine Videos sicher gespeichert und verfügbar',
                'Einfache Integration': 'Embed-Codes für nahtlose Website-Integration',
                'Flexible Verwaltung': 'Organisiere Videos nach Prioritäten',
                'StreamRec Integration': 'Direkte Uploads aus der StreamRec App'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'streamrec': {
            'name': 'StreamRec Studio',
            'icon': 'bi-mic',
            'color': 'info',
            'app_url': '/streamrec/',
            'short_desc': 'Bildschirm- und Audio-Aufnahme für Content Creation',
            'features': [
                'Browser-basierte Audio-Aufnahme',
                'Bildschirmaufnahme (in Entwicklung)',
                'Kamera-Zugriff für Recording',
                'Geräte-Erkennung und -Test',
                'VideoFlow-Integration für Uploads',
                'Multi-Stream Broadcasting (in Entwicklung)'
            ],
            'benefits': {
                'Einfache Bedienung': 'Direkt im Browser ohne Software-Installation',
                'Content Creation': 'Perfekt für Podcasts, Tutorials und Präsentationen',
                'Integrierte Lösung': 'Aufnehmen und direkt in VideoFlow hochladen',
                'Beta-Features': 'Ständige Weiterentwicklung neuer Aufnahme-Features'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'shopify': {
            'name': 'ShopifyFlow',
            'icon': 'bi-shop',
            'color': 'secondary',
            'app_url': '/shopify/',
            'short_desc': 'Shopify-Shop Management und Optimierung',
            'features': [
                'Multi-Shop Verwaltung',
                'Produkt-Import und -Synchronisation',
                'SEO-Optimierung für Produkte und Collections',
                'Alt-Text-Manager für Bilder',
                'Blog-Management',
                'Verkaufsanalysen und Kostentracking'
            ],
            'benefits': {
                'Zentrale Verwaltung': 'Verwalte mehrere Shopify-Shops von einer Plattform',
                'SEO-Optimierung': 'Verbessere deine Suchmaschinen-Rankings',
                'Zeitersparnis': 'Automatisiere wiederkehrende Shop-Management-Aufgaben',
                'Kostenübersicht': 'Behalte PayPal-Gebühren und andere Kosten im Blick'
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
        'bilder': {
            'name': 'ImageFlow Pro',
            'icon': 'bi-image',
            'color': 'primary',
            'short_desc': 'Professionelle Bildbearbeitung mit KI-Power',
            'features': [
                'KI-gestützte automatische Bildverbesserung',
                'Batch-Processing für Hunderte von Bildern',
                'Advanced Filter und Effekte',
                'Cloud-basierte Bildarchivierung'
            ],
            'benefits': {
                'Zeitersparnis': 'Bearbeite Bilder 10x schneller',
                'Professionelle Qualität': 'Studio-Qualität mit einem Klick'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'mail': {
            'name': 'MailFlow Enterprise',
            'icon': 'bi-envelope',
            'color': 'info',
            'short_desc': 'Intelligentes E-Mail-Management für Profis',
            'features': [
                'KI-basierte E-Mail-Sortierung und Priorisierung',
                'Automatische Antwort-Vorschläge',
                'Erweiterte Suchfunktionen',
                'Multi-Account Management'
            ],
            'benefits': {
                'Inbox Zero': 'Behalte deine E-Mails unter Kontrolle',
                'Maximale Effizienz': 'Spare täglich Stunden'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'schulungen': {
            'name': 'LernHub Pro',
            'icon': 'bi-graduation-cap',
            'color': 'success',
            'short_desc': 'Moderne Lern- und Schulungsplattform',
            'features': [
                'Interaktive Kurse und Tutorials',
                'Fortschrittstracking und Zertifikate',
                'Community-Features',
                'Mobile Learning'
            ],
            'benefits': {
                'Flexible Weiterbildung': 'Lerne in deinem Tempo',
                'Zertifiziert': 'Anerkannte Abschlüsse'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'somi_plan': {
            'name': 'PlanMaster Pro',
            'icon': 'bi-calendar-check',
            'color': 'warning',
            'short_desc': 'Intelligente Planung und Terminverwaltung',
            'features': [
                'KI-optimierte Terminplanung',
                'Ressourcenmanagement',
                'Team-Koordination',
                'Mobile Synchronisation'
            ],
            'benefits': {
                'Perfekte Organisation': 'Nie wieder Terminkonflikte',
                'Teamwork': 'Koordinierte Zusammenarbeit'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'loomads': {
            'name': 'AdFlow Pro',
            'icon': 'bi-megaphone',
            'color': 'danger',
            'short_desc': 'Intelligente Werbeplattform der nächsten Generation',
            'features': [
                'KI-optimierte Werbeschaltung',
                'Multi-Platform Kampagnen',
                'Real-time Analytics',
                'Automatisches Targeting'
            ],
            'benefits': {
                'ROI Maximum': 'Maximiere deinen Werbeerfolg',
                'Volle Kontrolle': 'Behalte den Überblick'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'promptpro': {
            'name': 'PromptPro',
            'icon': 'bi-collection',
            'color': 'info',
            'app_url': '/promptpro/',
            'short_desc': 'KI-Prompt-Bibliothek und Kategorisierung',
            'features': [
                'Prompt-Bibliothek erstellen und verwalten',
                'Kategorien für bessere Organisation',
                'Prompt-Templates speichern',
                'Einfache Suche und Verwaltung',
                'Team-Kollaboration (in Entwicklung)',
                'Performance-Analytics (in Entwicklung)'
            ],
            'benefits': {
                'Bessere Organisation': 'Alle deine KI-Prompts zentral verwaltet',
                'Zeit sparen': 'Wiederverwendbare Prompt-Templates',
                'Strukturiert arbeiten': 'Kategorien helfen beim schnellen Finden',
                'Beta-Entwicklung': 'Neue Features kommen regelmäßig dazu'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'myprompter': {
            'name': 'MyPrompter',
            'icon': 'bi-mic-fill',
            'color': 'warning',
            'app_url': '/myprompter/',
            'short_desc': 'Professioneller Teleprompter mit intelligenter Spracherkennung',
            'features': [
                'Automatische Spracherkennung (Deutsch)',
                'Intelligentes Scrolling folgt deiner Stimme',
                'Spiegel-Funktion für professionelle Teleprompter-Setups',
                'Flexible Textgröße (1.0 - 4.0 rem)',
                'Fullscreen-Modus mit Stats-Anzeige',
                'Texte speichern und laden',
                'Mobile-optimiert für unterwegs'
            ],
            'benefits': {
                'Perfekt für Content Creator': 'Ideal für Video-Aufnahmen, Präsentationen und Reden',
                'Professionelle Features': 'Spiegel-Funktion und anpassbare Textgröße',
                'Zeit sparen': 'Automatisches Scrolling, keine manuelle Steuerung nötig',
                'Volle Kontrolle': 'Wähle zwischen voller Stats-Anzeige oder reinem Text-Modus'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'loomconnect': {
            'name': 'LoomConnect',
            'icon': 'bi-people',
            'color': 'primary',
            'app_url': '/loomconnect/',
            'short_desc': 'Professionelles Kontakt- und CRM-System',
            'features': [
                'Kontaktverwaltung mit Kategorisierung',
                'CRM-Funktionen für Kundenbeziehungen',
                'Notizen und Aktivitäten-Tracking',
                'Import/Export von Kontakten',
                'Team-Collaboration'
            ],
            'benefits': {
                'Zentrales Kontaktmanagement': 'Alle Kontakte an einem Ort',
                'Bessere Kundenbeziehungen': 'Behalte den Überblick über alle Interaktionen',
                'Team-Zusammenarbeit': 'Teile Kontakte mit deinem Team'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'loomline': {
            'name': 'LoomLine',
            'icon': 'fas fa-list-alt',
            'color': 'primary',
            'app_url': '/loomline/',
            'short_desc': 'SEO-fokussiertes Aufgaben- und Projektmanagement',
            'features': [
                'Keyword-Tracking und -Planung',
                'Content-Kalender',
                'SEO-Aufgabenverwaltung',
                'Ranking-Überwachung',
                'Team-Collaboration'
            ],
            'benefits': {
                'SEO-Optimierung': 'Behalte alle SEO-Aufgaben im Blick',
                'Content-Planung': 'Plane deine Inhalte strategisch',
                'Team-Koordination': 'Arbeite effizient im Team'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'keyengine': {
            'name': 'KeyEngine',
            'icon': 'fas fa-key',
            'color': 'success',
            'app_url': '/keyengine/',
            'short_desc': 'Intelligente Keyword-Recherche und SEO-Analyse',
            'features': [
                'Keyword-Recherche mit Suchvolumen',
                'Wettbewerbsanalyse',
                'SERP-Analyse',
                'Content-Optimierungsvorschläge',
                'Keyword-Clustering'
            ],
            'benefits': {
                'Bessere Rankings': 'Finde die richtigen Keywords',
                'Wettbewerbsvorteil': 'Analysiere deine Konkurrenz',
                'Content-Strategie': 'Erstelle optimierte Inhalte'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'fileshare': {
            'name': 'FileShare',
            'icon': 'fas fa-share-alt',
            'color': 'info',
            'app_url': '/fileshare/',
            'short_desc': 'Sichere Dateifreigabe und Cloud-Speicher',
            'features': [
                'Drag & Drop Upload',
                'Ordnerstruktur',
                'Freigabe-Links mit Passwortschutz',
                'Dateiversionen',
                'Team-Kollaboration'
            ],
            'benefits': {
                'Sichere Speicherung': 'Deine Dateien sicher in der Cloud',
                'Einfache Freigabe': 'Teile Dateien mit nur einem Link',
                'Volle Kontrolle': 'Verwalte Zugriffsrechte'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'makeads': {
            'name': 'AdsMake',
            'icon': 'bi-megaphone',
            'color': 'warning',
            'app_url': '/makeads/',
            'short_desc': 'KI-gestützte Werbetexte und Anzeigen erstellen',
            'features': [
                'KI-Generierung von Werbetexten',
                'Verschiedene Anzeigenformate',
                'A/B-Test Vorschläge',
                'Multi-Platform Support',
                'Vorlagen-Bibliothek'
            ],
            'benefits': {
                'Schnelle Erstellung': 'Erstelle Anzeigen in Sekunden',
                'Bessere Performance': 'KI-optimierte Texte',
                'Zeit sparen': 'Keine stundenlange Kreativarbeit'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'ideopin': {
            'name': 'IdeoPin',
            'icon': 'bi-pinterest',
            'color': 'danger',
            'app_url': '/ideopin/',
            'short_desc': 'Pinterest-optimierte Pin-Generierung mit KI',
            'features': [
                'KI-generierte Pin-Designs',
                'Optimale Bildformate für Pinterest',
                'Keyword-optimierte Beschreibungen',
                'Batch-Erstellung',
                'Vorlagen und Stile'
            ],
            'benefits': {
                'Mehr Reichweite': 'Optimierte Pins für bessere Performance',
                'Zeit sparen': 'Automatische Pin-Erstellung',
                'Professionell': 'Hochwertige Designs'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'imageforge': {
            'name': 'ImageForge',
            'icon': 'bi-image',
            'color': 'primary',
            'app_url': '/imageforge/',
            'short_desc': 'KI-Bildgenerierung für professionelle Inhalte',
            'features': [
                'Text-zu-Bild Generierung',
                'Verschiedene Stile und Formate',
                'Bild-Bearbeitung mit KI',
                'Batch-Generierung',
                'Projekt-Verwaltung'
            ],
            'benefits': {
                'Einzigartige Bilder': 'Erstelle individuelle Grafiken',
                'Keine Designkenntnisse nötig': 'KI macht die Arbeit',
                'Unbegrenzte Kreativität': 'Generiere beliebige Motive'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'vskript': {
            'name': 'VSkript',
            'icon': 'bi-camera-video',
            'color': 'success',
            'app_url': '/vskript/',
            'short_desc': 'KI-Video-Skript-Generator für Content Creator',
            'features': [
                'Video-Skripte aus Keywords generieren',
                'Verschiedene Skript-Arten (Fun Facts, How-To, etc.)',
                'Plattform-Optimierung (YouTube, TikTok, Instagram)',
                'Ton und Zielgruppe anpassbar',
                'Länge einstellbar (15 Sek - 10 Min)'
            ],
            'benefits': {
                'Schnelle Content-Erstellung': 'Skripte in Sekunden',
                'Plattform-optimiert': 'Passt sich dem Format an',
                'Professionelle Qualität': 'KI-optimierte Texte'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'blogprep': {
            'name': 'BlogPrep',
            'icon': 'bi-pencil-square',
            'color': 'info',
            'app_url': '/blogprep/',
            'short_desc': 'KI-Blog-Artikel-Generator für Shopify',
            'features': [
                'Blog-Artikel aus Produkten generieren',
                'SEO-optimierte Inhalte',
                'Verschiedene Schreibstile',
                'Automatische Formatierung',
                'Direkte Shopify-Integration'
            ],
            'benefits': {
                'Content-Marketing': 'Erstelle regelmäßig Blog-Inhalte',
                'SEO-Boost': 'Optimierte Artikel für bessere Rankings',
                'Zeit sparen': 'KI schreibt für dich'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        }
    }
    
    # Filtere nur die Apps, die in der Datenbank als verfügbar markiert sind
    available_apps = {}

    # Verwende nur die App-Namen aus den available_permissions
    allowed_app_names = [p.app_name for p in available_permissions]

    for app_name, app_info in all_apps.items():
        if app_name in allowed_app_names:
            available_apps[app_name] = app_info

    return available_apps


def _get_all_apps():
    """Gibt ALLE App-Informationen zurück (ohne Filterung)"""
    # Alle App-Informationen (identisch mit all_apps in _get_available_apps)
    return {
        'todos': {
            'name': 'ToDo Manager',
            'icon': 'bi-list-check',
            'color': 'primary',
            'short_desc': 'Einfache und effektive Aufgabenverwaltung für Teams',
        },
        'organisation': {
            'name': 'WorkSpace',
            'icon': 'bi-building',
            'color': 'success',
            'short_desc': 'Organisiere Termine, Notizen und Ideen zentral',
        },
        'videos': {
            'name': 'VideoFlow',
            'icon': 'bi-play-circle',
            'color': 'danger',
            'short_desc': 'Einfaches Video-Hosting und -Management',
        },
        'streamrec': {
            'name': 'StreamRec Studio',
            'icon': 'bi-mic',
            'color': 'info',
            'short_desc': 'Bildschirm- und Audio-Aufnahme für Content Creation',
        },
        'shopify': {
            'name': 'ShopifyFlow',
            'icon': 'bi-shop',
            'color': 'secondary',
            'short_desc': 'Shopify-Shop Management und Optimierung',
        },
        'chat': {
            'name': 'ChatFlow Enterprise',
            'icon': 'bi-chat-dots',
            'color': 'warning',
            'short_desc': 'Next-Generation Business Communication Platform',
        },
        'bilder': {
            'name': 'ImageFlow Pro',
            'icon': 'bi-image',
            'color': 'primary',
            'short_desc': 'Professionelle Bildbearbeitung mit KI-Power',
        },
        'mail': {
            'name': 'MailFlow Enterprise',
            'icon': 'bi-envelope',
            'color': 'info',
            'short_desc': 'Intelligentes E-Mail-Management für Profis',
        },
        'schulungen': {
            'name': 'LernHub Pro',
            'icon': 'bi-graduation-cap',
            'color': 'success',
            'short_desc': 'Moderne Lern- und Schulungsplattform',
        },
        'somi_plan': {
            'name': 'SoMi-Plan',
            'icon': 'bi-calendar-check',
            'color': 'warning',
            'short_desc': 'Social Media Planung und Strategie',
        },
        'loomads': {
            'name': 'AdFlow Pro',
            'icon': 'bi-megaphone',
            'color': 'danger',
            'short_desc': 'Intelligente Werbeplattform der nächsten Generation',
        },
        'promptpro': {
            'name': 'PromptPro',
            'icon': 'bi-collection',
            'color': 'info',
            'short_desc': 'KI-Prompt-Bibliothek und Kategorisierung',
        },
        'myprompter': {
            'name': 'MyPrompter',
            'icon': 'bi-mic-fill',
            'color': 'warning',
            'short_desc': 'Professioneller Teleprompter mit intelligenter Spracherkennung',
        },
        'loomconnect': {
            'name': 'LoomConnect',
            'icon': 'bi-people',
            'color': 'primary',
            'short_desc': 'Professionelles Kontakt- und CRM-System',
        },
        'loomline': {
            'name': 'LoomLine',
            'icon': 'fas fa-list-alt',
            'color': 'primary',
            'short_desc': 'SEO-fokussiertes Aufgaben- und Projektmanagement',
        },
        'keyengine': {
            'name': 'KeyEngine',
            'icon': 'fas fa-key',
            'color': 'success',
            'short_desc': 'Intelligente Keyword-Recherche und SEO-Analyse',
        },
        'fileshare': {
            'name': 'FileShare',
            'icon': 'fas fa-share-alt',
            'color': 'info',
            'short_desc': 'Sichere Dateifreigabe und Cloud-Speicher',
        },
        'makeads': {
            'name': 'AdsMake',
            'icon': 'bi-megaphone',
            'color': 'warning',
            'short_desc': 'KI-gestützte Werbetexte und Anzeigen erstellen',
        },
        'ideopin': {
            'name': 'IdeoPin',
            'icon': 'bi-pinterest',
            'color': 'danger',
            'short_desc': 'Pinterest-optimierte Pin-Generierung mit KI',
        },
        'imageforge': {
            'name': 'ImageForge',
            'icon': 'bi-image',
            'color': 'primary',
            'short_desc': 'KI-Bildgenerierung für professionelle Inhalte',
        },
        'vskript': {
            'name': 'VSkript',
            'icon': 'bi-camera-video',
            'color': 'success',
            'short_desc': 'KI-Video-Skript-Generator für Content Creator',
        },
        'blogprep': {
            'name': 'BlogPrep',
            'icon': 'bi-pencil-square',
            'color': 'info',
            'short_desc': 'KI-Blog-Artikel-Generator für Shopify',
        },
    }


def public_app_info(request, app_name):
    """Öffentliche App-Info-Seiten für nicht angemeldete Benutzer"""
    # Verwende alle Apps (nicht gefiltert) für öffentliche Info-Seiten
    all_apps = _get_all_apps()

    # Fallback auf gefilterte Apps falls nicht in all_apps
    apps_info = _get_available_apps()

    app_data = all_apps.get(app_name) or apps_info.get(app_name)
    if not app_data:
        raise Http404("App nicht gefunden")
    
    # Get editable content if exists
    editable_content = {}
    if request.user.is_authenticated and request.user.is_superuser:
        editable_content = EditableContent.objects.filter(
            user=request.user, 
            page=f'app_info_{app_name}'
        ).order_by('sort_order', 'created_at')
    
    context = {
        'app_name': app_name,
        'app': app_data,
        'editable_content': editable_content,
        'is_public': not request.user.is_authenticated,  # True nur für nicht-angemeldete Benutzer
        'current_page': f'app_info_{app_name}'
    }
    
    return render(request, 'core/public_app_info.html', context)


def public_app_list(request):
    """Zeigt alle verfügbaren Apps für nicht angemeldete Benutzer"""
    apps_info = _get_available_apps()
    
    context = {
        'apps': apps_info,
        'is_public': not request.user.is_authenticated,  # True nur für nicht-angemeldete Benutzer
        'current_page': 'app_list'
    }
    
    return render(request, 'core/public_app_list.html', context)


def redirect_to_organization_chat(request):
    """Redirect von /chat/ zu /organization/chat/"""
    return redirect('organization:chat_home')


@login_required
def seo_dashboard(request):
    """SEO Dashboard als zentrale Übersicht für LoomLine und KeyEngine"""
    context = {
        'current_page': 'seo_dashboard',
        'loomline_data': {
            'name': 'LoomLine',
            'description': 'Aufgaben- und Projektmanagement mit SEO-Fokus',
            'icon': 'fas fa-list-alt',
            'color': 'primary',
            'features': [
                'Keyword-Tracking',
                'Content-Planung',
                'SEO-Aufgaben',
                'Ranking-Überwachung'
            ],
            'dashboard_url': 'loomline:dashboard',
            'projects_url': 'loomline:project-list',
        },
        'keyengine_data': {
            'name': 'KeyEngine',
            'description': 'Keyword-Recherche und SEO-Analyse',
            'icon': 'fas fa-key',
            'color': 'success',
            'features': [
                'Keyword-Recherche',
                'Wettbewerbsanalyse',
                'SERP-Analyse',
                'Content-Optimierung'
            ],
            'dashboard_url': 'keyengine:dashboard',
        }
    }
    return render(request, 'core/seo_dashboard.html', context)

def robots_txt(request):
    """
    SEO: robots.txt für Suchmaschinen
    Definiert welche Bereiche gecrawlt werden dürfen
    """
    from django.http import HttpResponse
    from django.urls import reverse

    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Hauptseiten",
        "Allow: /",
        "Allow: /apps/",
        "Allow: /impressum/",
        "Allow: /agb/",
        "Allow: /datenschutz/",
        "",
        "# Tools",
        "Allow: /beleuchtungsrechner/",
        "Allow: /din-en-13201/",
        "Allow: /licht/",
        "",
        "# Geschützte Bereiche - Kein Crawling",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /organization/",
        "Disallow: /chat/",
        "Disallow: /videos/",
        "Disallow: /api/",
        "Disallow: /mail/",
        "Disallow: /superconfig/",
        "Disallow: /payments/",
        "",
        "# Sitemap",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")

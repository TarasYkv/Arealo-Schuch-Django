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
    """Gibt ALLE App-Informationen zurück (ohne Filterung) - mit vollständigen Beschreibungen"""
    return {
        # === SEO Apps ===
        'seo_dashboard': {
            'name': 'SEO Dashboard',
            'icon': 'fas fa-chart-line',
            'color': 'primary',
            'short_desc': 'Dein SEO-Cockpit - alle SEO-Tools auf einen Blick.',
            'features': [
                'LoomLine-Integration - Deine SEO-Aufgaben im Überblick',
                'KeyEngine-Anbindung - Keyword-Recherche direkt starten',
                'QuestionFinder - Fragen deiner Zielgruppe finden',
                'Performance-Übersicht - Alle wichtigen Metriken',
                'Quick-Actions - Schnellzugriff auf häufige Aktionen',
                'Status-Widgets - Offene Tasks und Fortschritt'
            ],
            'benefits': {
                'Zentrale Übersicht': 'Alle SEO-Tools an einem Ort',
                'Schneller Einstieg': 'Direkt loslegen ohne Suchen',
                'Besserer Überblick': 'SEO-Status auf einen Blick',
                'Effizienter arbeiten': 'Weniger Klicks, mehr Ergebnisse'
            },
            'pricing': 'Kostenlos nutzbar',
            'url_name': 'seo_dashboard'
        },
        'loomline': {
            'name': 'LoomLine',
            'icon': 'fas fa-list-alt',
            'color': 'primary',
            'short_desc': 'SEO Content-Planung - plane, tracke und optimiere deine SEO-Inhalte systematisch.',
            'features': [
                'Content-Kalender - Plane Blogartikel, Landingpages und Updates im Voraus',
                'Keyword-Zuweisung - Ordne Ziel-Keywords zu jedem Content-Stück zu',
                'Status-Tracking - Verfolge den Fortschritt von Idee bis Veröffentlichung',
                'Priorisierung - Sortiere nach Wichtigkeit und SEO-Potenzial',
                'Team-Übersicht - Sehe wer an welchem Content arbeitet',
                'Deadline-Management - Verpasse keine Veröffentlichungstermine'
            ],
            'benefits': {
                'Struktur': 'Nie wieder chaotische Content-Planung',
                'Konsistenz': 'Regelmäßiger Content-Output für bessere Rankings',
                'Überblick': 'Alle SEO-Aufgaben auf einen Blick',
                'Effizienz': 'Schneller von der Idee zum fertigen Artikel'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'keyengine': {
            'name': 'KeyEngine',
            'icon': 'fas fa-key',
            'color': 'success',
            'short_desc': 'Keyword-Recherche leicht gemacht - finde die besten Keywords für deine Inhalte.',
            'features': [
                'Keyword-Suche - Finde relevante Keywords zu jedem Thema',
                'Suchvolumen-Daten - Sehe wie oft Keywords gesucht werden',
                'Keyword-Schwierigkeit - Erkenne wie schwer es ist zu ranken',
                'Verwandte Keywords - Entdecke ähnliche Suchbegriffe',
                'Keyword-Listen - Speichere und organisiere deine Recherchen',
                'Export-Funktion - Exportiere Keywords für andere Tools'
            ],
            'benefits': {
                'Bessere Rankings': 'Die richtigen Keywords für Top-Positionen',
                'Zeit sparen': 'Schnelle Recherche statt stundenlanges Suchen',
                'Datenbasiert': 'Entscheidungen auf echten Suchvolumen',
                'Wettbewerbsvorteil': 'Finde Keywords die andere übersehen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'questionfinder': {
            'name': 'QuestionFinder',
            'icon': 'fas fa-question-circle',
            'color': 'info',
            'short_desc': 'Finde echte Fragen deiner Zielgruppe - perfekt für FAQ und Content-Ideen.',
            'features': [
                'Fragen-Suche - Finde Fragen die Menschen wirklich stellen',
                'Quellen-Vielfalt - Fragen aus Google, Foren, Reddit und mehr',
                'Themen-Clustering - Gruppiere ähnliche Fragen automatisch',
                'FAQ-Generator - Erstelle FAQ-Sektionen aus gefundenen Fragen',
                'Content-Ideen - Jede Frage ist eine potenzielle Content-Idee',
                'Export - Speichere Fragen für die Content-Erstellung'
            ],
            'benefits': {
                'Echte Bedürfnisse': 'Beantworte was Menschen wirklich wissen wollen',
                'Featured Snippets': 'Frage-Antwort-Format für Position 0',
                'Content-Inspiration': 'Nie wieder Ideenmangel',
                'Zielgruppen-Verständnis': 'Verstehe was deine Nutzer bewegt'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },

        # === Media Apps ===
        'schulungen': {
            'name': 'Schulungen',
            'icon': 'bi-graduation-cap',
            'color': 'success',
            'short_desc': 'Erstelle KI-gestützte Schulungen - von der Idee zum fertigen Lernmaterial.',
            'features': [
                'KI-Schulungserstellung - Generiere komplette Schulungsinhalte aus Themen',
                'Kapitel-Struktur - Automatische Gliederung in logische Abschnitte',
                'Quiz-Generator - Erstelle Verständnisfragen zu jedem Kapitel',
                'Multi-Format - Text, Präsentationen und Handouts',
                'Anpassbare Tiefe - Von Grundlagen bis Expertenwissen',
                'Export-Optionen - PDF, PowerPoint und mehr'
            ],
            'benefits': {
                'Schnelle Erstellung': 'Schulungen in Minuten statt Tagen',
                'Professionell': 'Didaktisch sinnvolle Struktur durch KI',
                'Flexibel': 'Für jedes Thema und jede Zielgruppe',
                'Kosteneffizient': 'Kein teurer Instructional Designer nötig'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'bilder': {
            'name': 'Bilder',
            'icon': 'bi-image',
            'color': 'primary',
            'short_desc': 'Deine Bildverwaltung - organisiere, bearbeite und optimiere alle Bilder zentral.',
            'features': [
                'Bildverwaltung - Alle Bilder übersichtlich organisiert',
                'Ordner-Struktur - Kategorisiere nach Projekten oder Themen',
                'Schnelle Vorschau - Bilder ohne Download ansehen',
                'Basis-Bearbeitung - Zuschneiden, Drehen, Größe ändern',
                'Metadaten - Titel, Beschreibung und Tags hinzufügen',
                'Freigabe-Links - Bilder einfach teilen'
            ],
            'benefits': {
                'Übersicht': 'Alle Bilder an einem Ort',
                'Schneller Zugriff': 'Das richtige Bild sofort finden',
                'Organisation': 'Schluss mit Datei-Chaos',
                'Einfach teilen': 'Bilder mit einem Klick freigeben'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'videos': {
            'name': 'Videos',
            'icon': 'bi-play-circle',
            'color': 'danger',
            'short_desc': 'Video-Hosting für deine Inhalte - speichere, verwalte und teile Videos ohne Limits.',
            'features': [
                'Video-Upload - Lade Videos in allen gängigen Formaten hoch',
                'Streaming-Player - Flüssige Wiedergabe ohne Buffering',
                'Embed-Codes - Videos auf Websites und Blogs einbetten',
                'Shopify-Integration - Videos in Shopify-Blogs einbinden (ideal bei begrenztem Shopify-Speicher)',
                'Privatsphäre-Optionen - Öffentlich, nicht gelistet oder privat',
                'Speicher-Übersicht - Behalte deinen Verbrauch im Blick'
            ],
            'benefits': {
                'Unabhängig': 'Dein eigenes Video-Hosting ohne YouTube',
                'Shopify-Vorteil': 'Umgehe Shopify-Speicherlimits für Videos',
                'Professionell': 'Saubere Einbettung ohne fremde Werbung',
                'Volle Kontrolle': 'Du bestimmst wer deine Videos sieht'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'streamrec': {
            'name': 'StreamRec',
            'icon': 'bi-mic',
            'color': 'info',
            'short_desc': 'Aufnahme-Studio im Browser - nimm Bildschirm, Webcam und Audio professionell auf.',
            'features': [
                'Bildschirmaufnahme - Nimm deinen gesamten Bildschirm oder einzelne Fenster auf',
                'Multi-Screen-Recording - Mehrere Bildschirme oder Fenster gleichzeitig aufnehmen',
                'Webcam-Overlay - Kamera-Bild über die Aufnahme legen',
                'Hintergrund-Entfernung - Entferne Webcam-Hintergrund automatisch',
                'Format-Anpassung - Erstelle 9:16 für TikTok, 1:1 für Instagram, 16:9 für YouTube',
                'Audio-Aufnahme - Mikrofon und System-Audio getrennt aufnehmen',
                'Direkt posten - Videos direkt auf YouTube, TikTok und anderen Plattformen veröffentlichen',
                'Layout-Anordnung - Positioniere Bildschirme und Webcam frei im Video'
            ],
            'benefits': {
                'Alles in einem': 'Aufnahme, Bearbeitung und Posting in einem Tool',
                'Social Media Ready': 'Direkt im richtigen Format für jede Plattform',
                'Professionell aussehen': 'Hintergrund-Entfernung wie im TV-Studio',
                'Zeit sparen': 'Vom Aufnehmen direkt zum Veröffentlichen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'promptpro': {
            'name': 'PromptPro',
            'icon': 'bi-collection',
            'color': 'info',
            'short_desc': 'Deine Prompt-Bibliothek für KI-Tools - organisiere, optimiere und teile deine besten Prompts.',
            'features': [
                'Prompt-Bibliothek - Alle Prompts zentral organisiert und kategorisiert',
                'Tags & Kategorien - Schnelles Finden durch intelligente Verschlagwortung',
                'Favoriten & Bewertung - Markiere deine erfolgreichsten Prompts',
                'Ein-Klick-Kopieren - Prompts sofort in die Zwischenablage kopieren',
                'Variablen-System - Platzhalter für wiederverwendbare Prompt-Templates',
                'Team-Sharing - Teile Prompts mit deinem Team'
            ],
            'benefits': {
                'Effizienz steigern': 'Nie wieder Zeit mit Prompt-Suche verschwenden',
                'Qualität sichern': 'Bewährte Prompts immer griffbereit',
                'Wissen teilen': 'Best Practices im Team verbreiten',
                'Konsistenz': 'Einheitliche Ergebnisse durch standardisierte Prompts'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'myprompter': {
            'name': 'MyPrompter',
            'icon': 'bi-mic-fill',
            'color': 'warning',
            'short_desc': 'Dein digitaler Teleprompter - lies Texte professionell ab während du Videos aufnimmst.',
            'features': [
                'Automatisches Scrollen - Text scrollt in einstellbarer Geschwindigkeit mit',
                'Leseposition-Anzeige - Immer sichtbar wo du gerade im Text bist',
                'Geschwindigkeits-Kontrolle - Scroll-Tempo an dein Sprechtempo anpassen',
                'Schriftgröße anpassbar - Optimale Lesbarkeit auf jedem Bildschirm',
                'Pause & Fortsetzen - Jederzeit anhalten und weitermachen',
                'Vollbild-Modus - Maximale Konzentration ohne Ablenkung'
            ],
            'benefits': {
                'Professionelle Videos': 'Fließend sprechen ohne Versprecher oder Stocken',
                'Natürlicher Blickkontakt': 'Text nah an der Kamera für direkten Augenkontakt',
                'Zeitersparnis': 'Weniger Takes durch perfektes Ablesen',
                'Flexibel einsetzbar': 'Für YouTube, Präsentationen, Schulungen und mehr'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'fileshare': {
            'name': 'FileShare',
            'icon': 'fas fa-share-alt',
            'color': 'info',
            'short_desc': 'Sichere Dateiübertragung - teile Dateien einfach und sicher mit Kunden und Partnern.',
            'features': [
                'Download-Links erstellen - Generiere sichere Links für jede Datei',
                'Ablaufdatum setzen - Links automatisch nach bestimmter Zeit deaktivieren',
                'Passwortschutz - Zusätzliche Sicherheit durch optionales Passwort',
                'Download-Tracking - Sehe wer wann was heruntergeladen hat',
                'Mehrere Dateien - Mehrere Dateien in einem Transfer bündeln',
                'Speicher-Integration - Nutzt deinen WorkLoom-Speicherplatz'
            ],
            'benefits': {
                'Sicherheit': 'Kontrollierter Zugriff statt offener Cloud-Links',
                'Professionalität': 'Eigene Branding-Links statt WeTransfer & Co.',
                'Nachverfolgbar': 'Immer wissen ob Dateien angekommen sind',
                'DSGVO-konform': 'Daten auf deutschen/europäischen Servern'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },

        # === Shopify Apps ===
        'shopify': {
            'name': 'ShopifyFlow',
            'icon': 'bi-shop',
            'color': 'secondary',
            'short_desc': 'Verwalte deinen Shopify-Store intelligent - KI-gestützte SEO-Optimierung und detaillierte Backups.',
            'features': [
                'KI-generierte Alt-Texte - Automatische, SEO-optimierte Bildbeschreibungen per Knopfdruck',
                'KI-SEO-Texte - Meta-Titel und Meta-Beschreibungen von KI erstellen lassen',
                'Kategorie-Optimierung - Meta-Texte und Bilder für Collections SEO-optimieren',
                'Nur Meta-Felder - Produktinhalte bleiben unverändert, nur SEO-relevante Felder werden angepasst',
                'Detaillierte Backups - Sichere Produkte, Blogs, Bilder und alle Metadaten',
                'Flexible Wiederherstellung - Stelle einzelne Produkte, Blogs oder komplette Backups wieder her',
                'Element-Übersicht - Durchsuche alle gesicherten Produkte, Blogs und Bilder im Detail',
                'Backup-Verwaltung - Übersicht aller Backups mit Größe und Inhalt'
            ],
            'benefits': {
                'Besseres Ranking': 'KI-optimierte Meta-Felder für mehr organischen Traffic',
                'Sicher': 'Produkttexte und Preise bleiben unberührt, nur SEO-Daten ändern sich',
                'Granulare Kontrolle': 'Nur das wiederherstellen was du brauchst',
                'Zeitersparnis': 'KI schreibt Alt-Texte und Meta-Texte in Sekunden'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'blogprep': {
            'name': 'BlogPrep',
            'icon': 'bi-pencil-square',
            'color': 'info',
            'short_desc': 'KI-gestützte Blog-Erstellung - erstelle SEO-optimierte Blogartikel und Video-Skripte.',
            'features': [
                'KI-Blogartikel - Komplette Artikel aus Keywords oder Themen generieren',
                'Video-Skripte - Passende Skripte für Produkt- oder Erklärvideos erstellen',
                'SEO-Optimierung - Artikel automatisch für Suchmaschinen optimiert',
                'Keyword-Integration - Ziel-Keywords strategisch im Text platziert',
                'Meta-Daten - Titel und Beschreibungen automatisch generiert',
                'Shopify-Integration - Artikel direkt in deinen Shopify-Blog veröffentlichen',
                'Entwürfe speichern - Artikel als Entwurf speichern und später bearbeiten'
            ],
            'benefits': {
                'Content-Marketing leicht gemacht': 'Regelmäßige Blogartikel ohne Schreibblockade',
                'Mehr Traffic': 'SEO-optimierte Artikel bringen organische Besucher',
                'Zeit sparen': 'In Minuten statt Stunden zum fertigen Artikel',
                'Video & Text': 'Kombiniere Blog mit passendem Video-Content'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },

        # === Kreativ Apps ===
        'makeads': {
            'name': 'AdsMake',
            'icon': 'bi-megaphone',
            'color': 'warning',
            'short_desc': 'KI-Werbetexter - erstelle überzeugende Werbetexte, Anzeigen und Marketing-Content.',
            'features': [
                'Anzeigentexte - Google Ads, Facebook Ads, Instagram Ads generieren',
                'Headline-Generator - Aufmerksamkeitsstarke Überschriften erstellen',
                'Produktbeschreibungen - Verkaufsstarke Texte für deine Produkte',
                'Zielgruppen-Anpassung - Texte auf deine Zielgruppe zugeschnitten',
                'Varianten erstellen - Mehrere Versionen zum A/B-Testen',
                'Vorlagen - Bewährte Frameworks wie AIDA, PAS, BAB',
                'Mehrsprachig - Werbetexte in verschiedenen Sprachen'
            ],
            'benefits': {
                'Conversion steigern': 'Professionelle Werbetexte die verkaufen',
                'Schnell testen': 'Viele Varianten für A/B-Tests generieren',
                'Kosten sparen': 'Kein teurer Werbetexter nötig',
                'Konsistenz': 'Einheitliche Markenstimme über alle Kanäle'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'somi_plan': {
            'name': 'SoMi-Plan',
            'icon': 'bi-calendar-check',
            'color': 'warning',
            'short_desc': 'Social Media Planer - plane, erstelle und organisiere deinen Content für alle Netzwerke.',
            'features': [
                'Content-Kalender - Übersichtliche Planung deiner Posts im Kalender',
                'KI-Texterstellung - Passende Captions und Texte generieren lassen',
                'Medien-Verwaltung - Bilder und Videos für Posts organisieren',
                'Multi-Plattform - Plane für Instagram, Facebook, TikTok, LinkedIn & mehr',
                'Hashtag-Vorschläge - Relevante Hashtags automatisch vorgeschlagen',
                'Posting-Zeiten - Optimale Zeiten für maximale Reichweite',
                'Content-Ideen - KI-generierte Vorschläge für neue Posts'
            ],
            'benefits': {
                'Konsistenz': 'Regelmäßig posten durch vorausschauende Planung',
                'Zeitersparnis': 'Content im Voraus erstellen und planen',
                'Überblick': 'Alle Kanäle in einer Ansicht',
                'Nie ideenlos': 'KI liefert immer neue Content-Ideen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'ideopin': {
            'name': 'IdeoPin',
            'icon': 'bi-pinterest',
            'color': 'danger',
            'short_desc': 'Pinterest Pin Creator - erstelle, plane und veröffentliche Pins mit KI-Unterstützung.',
            'features': [
                'Pin-Design - Erstelle visuell ansprechende Pins im Pinterest-Format',
                'KI-Textgenerierung - Titel, Beschreibungen und Keywords von KI erstellen lassen',
                'Vorausplanen - Pins für später planen und automatisch veröffentlichen',
                'Bild-Optimierung - Bilder für Pinterest optimales Format anpassen',
                'Direkt posten - Pins sofort oder geplant auf Pinterest veröffentlichen',
                'Vorlagen - Bewährte Pin-Designs als Vorlage nutzen',
                'Link-Integration - Ziel-URLs für Traffic zu deiner Website',
                'Keyword-Optimierung - SEO-relevante Keywords für Pinterest-Suche'
            ],
            'benefits': {
                'Mehr Traffic': 'Pinterest als Traffic-Quelle für deine Website nutzen',
                'Zeitersparnis': 'KI schreibt Texte, du planst vor und bist fertig',
                'SEO-Vorteil': 'Pinterest Pins ranken auch bei Google',
                'Konsistenz': 'Regelmäßig Pins durch Vorausplanung'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'imageforge': {
            'name': 'ImageForge',
            'icon': 'bi-image',
            'color': 'primary',
            'short_desc': 'KI-Bildgenerator - erstelle professionelle Produktbilder, Mockups und Szenen.',
            'features': [
                'Nur Hintergrund - Generiere individuelle Hintergründe für deine Bilder',
                'Produkt + Hintergrund - Platziere dein Produkt in KI-generierten Szenen',
                'Charakter + Szene - Erstelle Personen in individuellen Umgebungen',
                'Charakter + Produkt - Kombiniere Personen mit deinen Produkten',
                'Mockup + Text - Erstelle Mockups mit integriertem Text und Branding',
                'Verschiedene Formate - Quadratisch, Hochformat, Querformat wählen',
                'Projekt-Verwaltung - Alle generierten Bilder organisiert speichern'
            ],
            'benefits': {
                'Professionelle Produktfotos': 'Ohne teures Fotoshooting oder Studio',
                'Flexibel': 'Der richtige Modus für jeden Anwendungsfall',
                'Einzigartig': 'Keine Stockfotos, 100% individuelle Bilder',
                'Schnell': 'Produktbilder in Sekunden statt Tagen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'vskript': {
            'name': 'VSkript',
            'icon': 'bi-camera-video',
            'color': 'success',
            'short_desc': 'Video-Skript-Generator - erstelle professionelle Skripte für YouTube, TikTok und mehr.',
            'features': [
                'KI-Skripterstellung - Komplette Video-Skripte aus Keywords generieren',
                'Plattform-Optimierung - Angepasst für YouTube, TikTok, Instagram, LinkedIn, Facebook',
                'Länge einstellbar - Von 15 Sekunden bis 10 Minuten',
                'Verschiedene Skript-Arten - How-To, Top-Listen, Fakten, Storys, Vergleiche und mehr',
                'Ton wählbar - Professionell, locker, humorvoll, inspirierend, provokant',
                'Zielgruppen-Anpassung - Anfänger, Fortgeschrittene, Experten, Allgemein',
                'Projekt-Verwaltung - Skripte speichern, bearbeiten und organisieren'
            ],
            'benefits': {
                'Nie wieder Schreibblockade': 'KI liefert fertige Skripte zum Ablesen',
                'Plattform-gerecht': 'Optimaler Stil für jede Social Media Plattform',
                'Schnell produzieren': 'Vom Thema zum fertigen Skript in Minuten',
                'Konsistent': 'Immer die richtige Ansprache für deine Zielgruppe'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },

        # === Organisation Apps ===
        'organisation': {
            'name': 'WorkSpace',
            'icon': 'bi-building',
            'color': 'success',
            'short_desc': 'Kollaborativer Arbeitsbereich - arbeite in Echtzeit mit deinem Team an Boards.',
            'features': [
                'Interaktive Boards - Visuelle Arbeitsflächen für Projekte und Brainstorming',
                'Echtzeit-Zusammenarbeit - Mehrere Personen arbeiten gleichzeitig am selben Board',
                'Live-Audio - Sprich mit allen Teilnehmern während der Board-Arbeit',
                'Live-Notizbereich - Gemeinsamer Textbereich für schnelle Notizen in Echtzeit',
                'Elemente platzieren - Bilder, Texte, Formen frei auf dem Board anordnen',
                'Zeichnen & Skizzieren - Freihand zeichnen und Ideen visualisieren',
                'Drag & Drop - Inhalte einfach per Drag & Drop positionieren',
                'Projekt-Organisation - Boards in Projekten und Kategorien organisieren'
            ],
            'benefits': {
                'Echte Zusammenarbeit': 'Wie im selben Raum, nur digital',
                'Keine Extra-Tools': 'Audio, Board und Notizen in einem',
                'Kreativ arbeiten': 'Ideen visuell entwickeln und teilen',
                'Ortsunabhängig': 'Team-Arbeit von überall'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'todos': {
            'name': 'ToDos',
            'icon': 'bi-list-check',
            'color': 'primary',
            'short_desc': 'Aufgabenverwaltung - behalte den Überblick über alle deine Aufgaben und Projekte.',
            'features': [
                'Aufgaben erstellen - Schnell neue Aufgaben mit Titel und Beschreibung anlegen',
                'Fälligkeitsdaten - Deadlines setzen und nie wieder Termine verpassen',
                'Kategorien & Tags - Aufgaben thematisch organisieren',
                'Prioritäten - Wichtige Aufgaben hervorheben',
                'Abhaken - Erledigte Aufgaben als fertig markieren',
                'Fortschritt - Übersicht wie viele Aufgaben erledigt sind',
                'Erinnerungen - Benachrichtigungen vor Fälligkeitsdatum'
            ],
            'benefits': {
                'Nichts vergessen': 'Alle Aufgaben an einem Ort',
                'Produktiver': 'Klare Übersicht was zu tun ist',
                'Stressfrei': 'Deadlines im Blick behalten',
                'Erfolgserlebnis': 'Fortschritt sichtbar machen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'chat': {
            'name': 'Chat',
            'icon': 'bi-chat-dots',
            'color': 'warning',
            'short_desc': 'Team-Kommunikation - chatte mit Teammitgliedern und halte alle Unterhaltungen an einem Ort.',
            'features': [
                'Direktnachrichten - Private Chats mit einzelnen Teammitgliedern',
                'Gruppenchats - Unterhaltungen mit mehreren Personen',
                'Datei-Anhänge - Bilder, Dokumente und Dateien im Chat teilen',
                'Benachrichtigungen - Nie eine wichtige Nachricht verpassen',
                'Chat-Suche - Alte Nachrichten schnell wiederfinden',
                'Nachrichtenverlauf - Komplette Chat-Historie gespeichert',
                'Emojis & Reaktionen - Nachrichten mit Emojis reagieren'
            ],
            'benefits': {
                'Schnelle Kommunikation': 'Kurze Wege statt langer E-Mails',
                'Alles an einem Ort': 'Keine verstreuten WhatsApp-Gruppen',
                'Dateien teilen': 'Dokumente direkt im Chat besprechen',
                'Team verbinden': 'Einfache Kommunikation mit allen Kollegen'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'mail': {
            'name': 'Email',
            'icon': 'bi-envelope',
            'color': 'info',
            'short_desc': 'E-Mail-Client - verwalte deine E-Mails direkt in WorkLoom ohne App-Wechsel.',
            'features': [
                'Posteingang - Alle E-Mails übersichtlich in einer Inbox',
                'E-Mails schreiben - Neue Nachrichten direkt verfassen und senden',
                'Anhänge - Dateien an E-Mails anhängen und empfangen',
                'Ordner & Labels - E-Mails organisieren und kategorisieren',
                'Suche - E-Mails nach Absender, Betreff oder Inhalt durchsuchen',
                'Zoho Mail Integration - Verbinde dein bestehendes E-Mail-Konto',
                'E-Mail-Vorlagen - Häufige Antworten als Vorlage speichern'
            ],
            'benefits': {
                'Alles in einem': 'E-Mails und Arbeit in einer Oberfläche',
                'Kein Kontextwechsel': 'Weniger App-Wechsel, mehr Fokus',
                'Übersichtlich': 'Klare Struktur für deine Kommunikation',
                'Verbunden': 'Bestehende E-Mail-Konten einfach integrieren'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'loomconnect': {
            'name': 'LoomConnect',
            'icon': 'bi-people',
            'color': 'primary',
            'short_desc': 'Business-Netzwerk - vernetze dich, teile Fähigkeiten und finde Experten für Zusammenarbeit.',
            'features': [
                'Profil erstellen - Präsentiere dich mit Bio, Standort, Website und Verfügbarkeitsstatus',
                'Fähigkeiten anbieten - Liste deine Skills mit Erfahrungslevel (Anfänger bis Profi)',
                'Experten finden - Suche nach Personen mit bestimmten Fähigkeiten',
                'Feed & Posts - Teile Updates, Fragen, Erfolge oder Skill-Angebote',
                'Connect-Anfragen - Vernetze dich für Skill-Tausch, Hilfe oder Zusammenarbeit',
                'Stories - 24-Stunden-Stories für schnelle Updates',
                'Kommentare & Likes - Interagiere mit Posts anderer Nutzer',
                'Profil-Statistiken - Sehe wer dein Profil besucht hat'
            ],
            'benefits': {
                'Richtige Kontakte': 'Finde genau die Experten die du brauchst',
                'Skill-Tausch': 'Tausche Fähigkeiten statt Geld',
                'Community': 'Werde Teil eines professionellen Netzwerks',
                'Sichtbarkeit': 'Zeige deine Expertise und werde gefunden'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!'
        },
        'linkloom': {
            'name': 'LinkLoom',
            'icon': 'fas fa-link',
            'color': 'primary',
            'short_desc': 'Link in Bio - erstelle deine persönliche Link-Seite mit eigenem URL und teile alle wichtigen Links.',
            'features': [
                'Eigener URL-Slug - Deine persönliche Adresse (workloom.de/l/dein-name)',
                'Unbegrenzte Links - Füge beliebig viele Links mit Beschreibungen hinzu',
                'Social Media Icons - Instagram, TikTok, YouTube, Twitter und mehr',
                'Profilbild & Beschreibung - Personalisiere deine Seite',
                'Eigenes Impressum - Für rechtliche Konformität in Deutschland',
                'Klick-Statistiken - Sehe welche Links am häufigsten geklickt werden',
                'Anpassbares Design - Wähle Farben für Hintergrund, Buttons und Text',
                'Live-Vorschau - Sehe Änderungen sofort beim Bearbeiten',
                'DSGVO-konform - Anonymisiertes Click-Tracking'
            ],
            'benefits': {
                'Ein Link für alles': 'Teile einen Link statt vieler',
                'Perfekt für Social Media': 'Der ideale Bio-Link für Instagram & Co.',
                'Professioneller Auftritt': 'Eigene gebrandete Link-Seite',
                'Rechtssicher': 'Eigenes Impressum für Deutschland'
            },
            'pricing': 'Kostenlos in der Beta-Phase - Jetzt registrieren und testen!',
            'url_name': 'linkloom:dashboard'
        },

        # === Legacy/Fallback entries ===
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


# ============================================
# Social Page (Link in Bio)
# ============================================

def social_page_view(request):
    """
    Öffentliche Social Page (Link in Bio)
    Ähnlich wie Linktree/Wonderlink
    """
    from superconfig.models import SocialPageConfig
    from django.http import HttpResponseNotFound

    config = SocialPageConfig.objects.first()
    if not config or not config.is_active:
        return HttpResponseNotFound("Seite nicht gefunden")

    icons = config.icons.filter(is_active=True).order_by('sort_order')
    buttons = config.buttons.filter(is_active=True).order_by('sort_order')

    return render(request, 'core/social_page.html', {
        'config': config,
        'icons': icons,
        'buttons': buttons,
    })


def social_button_click(request, button_id):
    """
    Trackt Button-Klick und leitet weiter
    DSGVO-konform: IP wird anonymisiert
    """
    from superconfig.models import SocialPageButton, SocialPageClick
    from django.shortcuts import redirect, get_object_or_404
    from django.utils import timezone
    from django.db.models import F

    button = get_object_or_404(SocialPageButton, id=button_id, is_active=True)

    # IP anonymisieren (DSGVO-konform)
    def anonymize_ip(ip):
        if not ip:
            return '0.0.0.0'
        if '.' in ip and ':' not in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                parts[3] = '0'
                return '.'.join(parts)
        if ':' in ip:
            parts = ip.split(':')
            if len(parts) >= 3:
                return ':'.join(parts[:3]) + '::0'
        return '0.0.0.0'

    # Client IP ermitteln
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')

    # Klick speichern
    SocialPageClick.objects.create(
        button=button,
        ip_address=anonymize_ip(ip),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referer=request.META.get('HTTP_REFERER', '')[:200] if request.META.get('HTTP_REFERER') else ''
    )

    # Counter erhöhen
    button.click_count = F('click_count') + 1
    button.last_clicked = timezone.now()
    button.save(update_fields=['click_count', 'last_clicked'])

    return redirect(button.url)

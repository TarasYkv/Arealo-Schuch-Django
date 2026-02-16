"""
Management Command zum Erstellen/Aktualisieren von App-Beschreibungen
für alle öffentlich sichtbaren Apps.

Usage: python manage.py setup_app_descriptions
"""

from django.core.management.base import BaseCommand
from accounts.models import AppInfo


class Command(BaseCommand):
    help = 'Erstellt oder aktualisiert App-Beschreibungen für alle sichtbaren Apps'

    def handle(self, *args, **options):
        # Alle App-Beschreibungen im professionellen Format
        app_descriptions = {
            'videos': {
                'title': 'VideoFlow - Professionelles Video-Hosting für Shopify & Webprojekte',
                'icon_class': 'bi bi-play-circle',
                'short_description': 'Unbegrenztes Video-Hosting ohne Upload-Limits',
                'detailed_description': '''Das Problem: Shopify und viele Webserver haben strikte Limits bei Video-Uploads. Wenige Videos erlaubt, begrenzter Speicherplatz, teure Upgrades.

Die Workloom-Lösung: Unbegrenztes Hosting PLUS Austausch mit Gleichgesinnten - teile Erfahrungen und knüpfe Kontakte!

So funktioniert's:
1️⃣ Video hochladen
2️⃣ Embed-Code oder Link generieren
3️⃣ In Shopify/Website einbinden

Technische Lösung trifft Community - gemeinsam wachsen mit Workloom!''',
                'key_features': [
                    'Unbegrenzter Video-Upload',
                    'Embed-Codes für jede Website',
                    'Öffentliche und private Video-Links',
                    'Video-Archivierung mit Prioritäten',
                    'Direkte StreamRec-Integration'
                ]
            },
            'streamrec': {
                'title': 'StreamRec - Browser-basierte Aufnahmen ohne Software',
                'icon_class': 'bi bi-mic',
                'short_description': 'Bildschirm- und Audio-Aufnahme direkt im Browser',
                'detailed_description': '''Das Problem: Für professionelle Aufnahmen braucht man teure Software, komplizierte Einrichtung und technisches Know-how.

Die Workloom-Lösung: StreamRec läuft komplett im Browser - keine Installation, keine Konfiguration, sofort loslegen!

So funktioniert's:
1️⃣ Browser öffnen und Gerät auswählen
2️⃣ Aufnahme starten (Bildschirm/Kamera/Audio)
3️⃣ Direkt in VideoFlow hochladen

Professionelle Aufnahmen für jeden - ohne technische Hürden!''',
                'key_features': [
                    'Browser-basierte Aufnahme',
                    'Bildschirm, Kamera & Audio',
                    'Keine Software-Installation',
                    'Direkte VideoFlow-Integration',
                    'Mobile-optimiert'
                ]
            },
            'chat': {
                'title': 'ChatFlow - Schnelle Team-Kommunikation',
                'icon_class': 'bi bi-chat-dots',
                'short_description': 'Echtzeit-Messaging für Teams und Projekte',
                'detailed_description': '''Das Problem: E-Mails sind zu langsam, WhatsApp zu privat, Slack zu teuer. Teams brauchen eine einfache Kommunikationslösung.

Die Workloom-Lösung: ChatFlow vereint schnelles Messaging mit Team-Workspaces - kostenlos und datenschutzkonform!

So funktioniert's:
1️⃣ Kanäle oder Direktchats erstellen
2️⃣ Nachrichten, Dateien und Links teilen
3️⃣ In Echtzeit zusammenarbeiten

Kommunikation, die Projekte voranbringt!''',
                'key_features': [
                    'Echtzeit-Messaging',
                    'Team-Workspaces & Kanäle',
                    'Dateifreigabe',
                    'DSGVO-konforme Server',
                    'Ende-zu-Ende Verschlüsselung'
                ]
            },
            'todos': {
                'title': 'ToDo Manager - Aufgaben effektiv verwalten',
                'icon_class': 'bi bi-list-check',
                'short_description': 'Einfache Aufgabenverwaltung für Teams',
                'detailed_description': '''Das Problem: Aufgaben gehen unter, Deadlines werden vergessen, Teams verlieren den Überblick über ihre Projekte.

Die Workloom-Lösung: Ein intuitiver Task-Manager, der Teams organisiert hält - ohne komplizierte Einrichtung!

So funktioniert's:
1️⃣ Listen und Aufgaben erstellen
2️⃣ Aufgaben zuweisen und Deadlines setzen
3️⃣ Fortschritt tracken und abhaken

Weniger Chaos, mehr Produktivität!''',
                'key_features': [
                    'To-Do-Listen erstellen',
                    'Aufgaben zuweisen',
                    'Deadlines und Erinnerungen',
                    'Status-Updates',
                    'Team-Kollaboration'
                ]
            },
            'organisation': {
                'title': 'WorkSpace - Zentrale Organisation',
                'icon_class': 'bi bi-building',
                'short_description': 'Termine, Notizen und Ideen an einem Ort',
                'detailed_description': '''Das Problem: Notizen in Apps, Termine im Kalender, Ideen auf Zetteln - alles verstreut und schwer zu finden.

Die Workloom-Lösung: WorkSpace vereint alles an einem Ort - Notizen, Kalender, Ideenboards und Team-Calls!

So funktioniert's:
1️⃣ Notizen erstellen und organisieren
2️⃣ Termine im integrierten Kalender planen
3️⃣ Ideen auf digitalen Boards sammeln

Alles Wichtige immer griffbereit!''',
                'key_features': [
                    'Notizen mit Ordnern',
                    'Kalender mit Terminerstellung',
                    'Digitale Ideenboards',
                    'Video-/Audio-Calls',
                    'Team-Kollaboration'
                ]
            },
            'shopify': {
                'title': 'ShopifyFlow - Multi-Shop Management',
                'icon_class': 'bi bi-shop',
                'short_description': 'Alle Shopify-Shops zentral verwalten',
                'detailed_description': '''Das Problem: Mehrere Shopify-Shops bedeutet mehrere Logins, manuelles Kopieren von Produkten und verlorene Zeit.

Die Workloom-Lösung: ShopifyFlow verbindet alle deine Shops - verwalte Produkte, SEO und Inhalte von einer Plattform!

So funktioniert's:
1️⃣ Shops mit API verbinden
2️⃣ Produkte und Collections verwalten
3️⃣ SEO optimieren und synchronisieren

Ein Dashboard für alle Shops!''',
                'key_features': [
                    'Multi-Shop Verwaltung',
                    'Produkt-Synchronisation',
                    'SEO-Optimierung',
                    'Alt-Text-Manager',
                    'Blog-Management',
                    'Verkaufsanalysen'
                ]
            },
            'bilder': {
                'title': 'ImageFlow - Professionelle Bildverwaltung',
                'icon_class': 'bi bi-image',
                'short_description': 'Bilder organisieren, bearbeiten und teilen',
                'detailed_description': '''Das Problem: Bilder sind überall verstreut, Bearbeitung ist aufwendig, und das Teilen umständlich.

Die Workloom-Lösung: ImageFlow bietet Bildverwaltung, Bearbeitung und Sharing in einer App!

So funktioniert's:
1️⃣ Bilder hochladen und organisieren
2️⃣ Mit integrierten Tools bearbeiten
3️⃣ Per Link oder Embed teilen

Deine Bildbibliothek in der Cloud!''',
                'key_features': [
                    'Cloud-Bildarchivierung',
                    'Batch-Bearbeitung',
                    'Filter und Effekte',
                    'Einfaches Sharing',
                    'Ordner-Organisation'
                ]
            },
            'mail': {
                'title': 'MailFlow - E-Mail-Kampagnen leicht gemacht',
                'icon_class': 'bi bi-envelope',
                'short_description': 'E-Mails verwalten und Kampagnen erstellen',
                'detailed_description': '''Das Problem: E-Mail-Marketing ist kompliziert, teuer und zeitaufwendig.

Die Workloom-Lösung: MailFlow macht E-Mail-Kampagnen einfach - von der Verwaltung bis zum Versand!

So funktioniert's:
1️⃣ E-Mail-Templates erstellen
2️⃣ Empfänger auswählen
3️⃣ Kampagne versenden und tracken

Professionelles E-Mail-Marketing ohne Komplexität!''',
                'key_features': [
                    'E-Mail-Kampagnen',
                    'Template-Editor',
                    'Empfänger-Verwaltung',
                    'Versand-Tracking',
                    'Multi-Account Support'
                ]
            },
            'schulungen': {
                'title': 'LernHub - Kurse erstellen und lernen',
                'icon_class': 'bi bi-graduation-cap',
                'short_description': 'Schulungen und Trainings für Teams',
                'detailed_description': '''Das Problem: Wissen im Team teilen ist schwierig. Schulungen sind zeitaufwendig und schlecht organisiert.

Die Workloom-Lösung: LernHub macht Wissenstransfer einfach - erstelle Kurse und tracke den Fortschritt!

So funktioniert's:
1️⃣ Kursinhalte erstellen (Text, Video, Quiz)
2️⃣ Teammitglieder einladen
3️⃣ Fortschritt tracken und Zertifikate vergeben

Wissen teilen war nie einfacher!''',
                'key_features': [
                    'Kurse erstellen',
                    'Video-Integration',
                    'Quiz und Tests',
                    'Fortschrittstracking',
                    'Zertifikate'
                ]
            },
            'somi_plan': {
                'title': 'SoMi-Plan - Social Media Content planen',
                'icon_class': 'bi bi-calendar-check',
                'short_description': 'Content-Kalender für Social Media',
                'detailed_description': '''Das Problem: Social Media Posting ist chaotisch - mal zu viel, mal vergessen, nie konsistent.

Die Workloom-Lösung: SoMi-Plan gibt dir den Überblick - plane Posts im Voraus und bleibe konsistent!

So funktioniert's:
1️⃣ Content-Ideen im Kalender eintragen
2️⃣ Posts planen und organisieren
3️⃣ Übersicht über alle Kanäle behalten

Nie wieder spontan posten müssen!''',
                'key_features': [
                    'Content-Kalender',
                    'Multi-Plattform Übersicht',
                    'Post-Planung',
                    'Ideensammlung',
                    'Team-Koordination'
                ]
            },
            'promptpro': {
                'title': 'PromptPro - KI-Prompt-Bibliothek',
                'icon_class': 'bi bi-collection',
                'short_description': 'Deine besten Prompts organisiert und wiederverwendbar',
                'detailed_description': '''Das Problem: Gute KI-Prompts gehen verloren, müssen immer wieder neu geschrieben werden.

Die Workloom-Lösung: PromptPro speichert deine besten Prompts - kategorisiert, durchsuchbar, sofort wiederverwendbar!

So funktioniert's:
1️⃣ Prompts speichern und kategorisieren
2️⃣ Mit Tags und Notizen organisieren
3️⃣ Bei Bedarf schnell finden und nutzen

Deine Prompt-Bibliothek für maximale KI-Effizienz!''',
                'key_features': [
                    'Prompt-Bibliothek',
                    'Kategorien und Tags',
                    'Schnellsuche',
                    'Templates speichern',
                    'Team-Sharing'
                ]
            },
            'myprompter': {
                'title': 'MyPrompter - Digitaler Teleprompter',
                'icon_class': 'bi bi-mic-fill',
                'short_description': 'Professioneller Teleprompter mit Spracherkennung',
                'detailed_description': '''Das Problem: Beim Sprechen vor der Kamera Text ablesen ohne dass man es merkt ist schwierig ohne Profi-Equipment.

Die Workloom-Lösung: MyPrompter ist ein digitaler Teleprompter mit intelligenter Spracherkennung - scrollt automatisch mit deiner Stimme!

So funktioniert's:
1️⃣ Text eingeben oder laden
2️⃣ Teleprompter starten
3️⃣ Sprechen - das Scrolling folgt deiner Stimme

Professionelle Videos wie ein News-Anchor!''',
                'key_features': [
                    'Automatische Spracherkennung',
                    'Intelligentes Scrolling',
                    'Spiegel-Modus',
                    'Flexible Textgröße',
                    'Fullscreen-Modus'
                ]
            },
            'fileshare': {
                'title': 'FileShare - Dateien sicher teilen',
                'icon_class': 'fas fa-share-alt',
                'short_description': 'Cloud-Speicher mit einfacher Freigabe',
                'detailed_description': '''Das Problem: Große Dateien per E-Mail versenden geht nicht. Cloud-Dienste sind kompliziert oder teuer.

Die Workloom-Lösung: FileShare bietet einfaches Upload und Teilen - mit Passwortschutz und Ablaufdatum!

So funktioniert's:
1️⃣ Datei per Drag & Drop hochladen
2️⃣ Freigabe-Link generieren
3️⃣ Optional mit Passwort schützen

Dateien teilen ohne Kompromisse!''',
                'key_features': [
                    'Drag & Drop Upload',
                    'Passwortgeschützte Links',
                    'Ablaufdatum setzen',
                    'Ordner-Struktur',
                    'Download-Tracking'
                ]
            },
            'loomconnect': {
                'title': 'LoomConnect - Business-Netzwerk & CRM',
                'icon_class': 'bi bi-people',
                'short_description': 'Kontakte verwalten und Beziehungen pflegen',
                'detailed_description': '''Das Problem: Visitenkarten stapeln sich, Kontakte sind überall verstreut, Follow-ups werden vergessen.

Die Workloom-Lösung: LoomConnect ist dein persönliches CRM - Kontakte zentral, Interaktionen dokumentiert, nichts geht verloren!

So funktioniert's:
1️⃣ Kontakte anlegen oder importieren
2️⃣ Notizen und Aktivitäten dokumentieren
3️⃣ Follow-ups planen und umsetzen

Networking, das funktioniert!''',
                'key_features': [
                    'Kontaktverwaltung',
                    'CRM-Funktionen',
                    'Notizen & Aktivitäten',
                    'Import/Export',
                    'Team-Sharing'
                ]
            },
            'linkloom': {
                'title': 'LinkLoom - Link in Bio für Social Media',
                'icon_class': 'bi bi-link-45deg',
                'short_description': 'Eine Seite für alle deine wichtigen Links',
                'detailed_description': '''Das Problem: Instagram, TikTok & Co. erlauben nur einen Link - aber du hast viele wichtige Seiten.

Die Workloom-Lösung: LinkLoom erstellt deine persönliche Link-Seite - alle wichtigen Links auf einer schönen Seite!

So funktioniert's:
1️⃣ Links hinzufügen und sortieren
2️⃣ Design anpassen
3️⃣ Link in Bio einsetzen

Alle Links - eine URL!''',
                'key_features': [
                    'Unbegrenzte Links',
                    'Anpassbares Design',
                    'Klick-Statistiken',
                    'Social Media Icons',
                    'Eigene URL'
                ]
            },
            'makeads': {
                'title': 'AdsMake - KI-Werbetexte in Sekunden',
                'icon_class': 'bi bi-megaphone',
                'short_description': 'Werbetexte automatisch generieren lassen',
                'detailed_description': '''Das Problem: Gute Werbetexte schreiben kostet Zeit. A/B-Tests manuell zu erstellen ist aufwendig.

Die Workloom-Lösung: AdsMake generiert mit KI in Sekunden verkaufsstarke Werbetexte - für alle Plattformen!

So funktioniert's:
1️⃣ Produkt/Service beschreiben
2️⃣ Plattform und Stil wählen
3️⃣ KI generiert mehrere Varianten

Werbetexte wie vom Profi - in Sekunden!''',
                'key_features': [
                    'KI-Textgenerierung',
                    'Mehrere Varianten',
                    'Plattform-optimiert',
                    'A/B-Test Vorschläge',
                    'Vorlagen-Bibliothek'
                ]
            },
            'ideopin': {
                'title': 'IdeoPin - Pinterest Pins mit KI',
                'icon_class': 'bi bi-pinterest',
                'short_description': 'Pinterest-optimierte Grafiken automatisch erstellen',
                'detailed_description': '''Das Problem: Pinterest braucht ständig neue Pins - aber Design dauert ewig.

Die Workloom-Lösung: IdeoPin erstellt Pinterest-optimierte Grafiken mit KI - im richtigen Format, mit perfektem Text!

So funktioniert's:
1️⃣ Thema und Keywords eingeben
2️⃣ Stil und Format wählen
3️⃣ KI erstellt Pin-Designs

Pinterest-Marketing auf Autopilot!''',
                'key_features': [
                    'KI-generierte Pins',
                    'Optimales Pinterest-Format',
                    'Keyword-optimierte Texte',
                    'Batch-Erstellung',
                    'Verschiedene Stile'
                ]
            },
            'imageforge': {
                'title': 'ImageForge - KI-Bilder generieren',
                'icon_class': 'bi bi-image',
                'short_description': 'Bilder aus Text erstellen mit KI',
                'detailed_description': '''Das Problem: Einzigartige Bilder für Marketing sind teuer - Stockfotos nutzt jeder.

Die Workloom-Lösung: ImageForge generiert mit KI einzigartige Bilder aus deiner Beschreibung - keine Lizenzprobleme!

So funktioniert's:
1️⃣ Bild beschreiben
2️⃣ Stil und Format wählen
3️⃣ KI generiert das Bild

Einzigartige Bilder für dein Marketing!''',
                'key_features': [
                    'Text-zu-Bild Generierung',
                    'Verschiedene Stile',
                    'Kommerzielle Nutzung',
                    'Batch-Generierung',
                    'Projekt-Verwaltung'
                ]
            },
            'vskript': {
                'title': 'VSkript - Video-Skripte mit KI',
                'icon_class': 'bi bi-camera-video',
                'short_description': 'Professionelle Video-Skripte automatisch erstellen',
                'detailed_description': '''Das Problem: Video-Content braucht gute Skripte - aber Schreiben ist zeitaufwendig.

Die Workloom-Lösung: VSkript generiert Video-Skripte für YouTube, TikTok, Instagram - angepasst an Länge und Stil!

So funktioniert's:
1️⃣ Thema und Keywords eingeben
2️⃣ Plattform und Länge wählen
3️⃣ KI schreibt das komplette Skript

Vom Thema zum fertigen Skript in Minuten!''',
                'key_features': [
                    'KI-Skript-Generator',
                    'Plattform-optimiert',
                    'Einstellbare Länge',
                    'Verschiedene Formate',
                    'Ton anpassbar'
                ]
            },
            'questionfinder': {
                'title': 'QuestionFinder - Fragen deiner Zielgruppe',
                'icon_class': 'bi bi-question-circle',
                'short_description': 'Finde heraus, was Menschen zu deinem Thema fragen',
                'detailed_description': '''Das Problem: Für guten Content brauchst du die Fragen deiner Zielgruppe - aber wo findest du sie?

Die Workloom-Lösung: QuestionFinder durchsucht das Web nach echten Fragen zu deinem Keyword!

So funktioniert's:
1️⃣ Keyword eingeben
2️⃣ Fragen analysieren lassen
3️⃣ Content-Ideen erhalten

Content, der Fragen beantwortet = Content, der rankt!''',
                'key_features': [
                    'Fragen-Recherche',
                    'Keyword-basiert',
                    'Quellen-Analyse',
                    'Export-Funktion',
                    'Content-Inspiration'
                ]
            },
            'blogprep': {
                'title': 'BlogPrep - Blog-Artikel für Shopify',
                'icon_class': 'bi bi-pencil-square',
                'short_description': 'SEO-optimierte Blog-Artikel aus Produkten generieren',
                'detailed_description': '''Das Problem: Ein Shopify-Blog braucht regelmäßig Content - aber Artikel schreiben kostet Zeit.

Die Workloom-Lösung: BlogPrep generiert Blog-Artikel aus deinen Shopify-Produkten - SEO-optimiert und im richtigen Format!

So funktioniert's:
1️⃣ Produkt oder Thema auswählen
2️⃣ Stil und Keywords festlegen
3️⃣ KI schreibt den Artikel

Blog-Content auf Knopfdruck!''',
                'key_features': [
                    'Artikel-Generator',
                    'SEO-optimiert',
                    'Shopify-Integration',
                    'Verschiedene Stile',
                    'Automatische Formatierung'
                ]
            },
            'android_apk_manager': {
                'title': 'APK Manager - Android Apps verteilen',
                'icon_class': 'bi bi-android2',
                'short_description': 'Android Apps hosten und ohne Play Store verteilen',
                'detailed_description': '''Das Problem: Interne Apps oder Beta-Versionen im Play Store zu verwalten ist kompliziert.

Die Workloom-Lösung: APK Manager ist dein privater App-Store - lade APKs hoch und teile sie per Link!

So funktioniert's:
1️⃣ APK-Datei hochladen
2️⃣ Beschreibung und Screenshots hinzufügen
3️⃣ Download-Link teilen

App-Distribution ohne Bürokratie!''',
                'key_features': [
                    'APK-Upload',
                    'Versionsverwaltung',
                    'Screenshot-Galerie',
                    'Öffentliche Links',
                    'Changelog-Support'
                ]
            },
            'desktop_app_manager': {
                'title': 'Desktop App Manager - Desktop Apps verteilen',
                'icon_class': 'bi bi-pc-display',
                'short_description': 'Desktop-Anwendungen (EXE) hosten, verteilen und updaten',
                'detailed_description': '''Das Problem: Desktop-Anwendungen an Nutzer zu verteilen und Updates bereitzustellen ist umständlich.

Die Workloom-Lösung: Desktop App Manager ist dein privater Software-Store - lade EXEs hoch und verteile sie mit automatischer Update-Prüfung!

So funktioniert's:
1️⃣ EXE-Datei hochladen
2️⃣ Beschreibung und Screenshots hinzufügen
3️⃣ Download-Link teilen - Updates werden automatisch erkannt

Software-Distribution mit Auto-Update!''',
                'key_features': [
                    'EXE-Upload',
                    'Versionsverwaltung',
                    'Auto-Update API',
                    'Screenshot-Galerie',
                    'Download-Statistiken'
                ]
            },
            'backloom': {
                'title': 'BackLoom - RSS Feed Management',
                'icon_class': 'bi bi-rss',
                'short_description': 'RSS-Feeds erstellen und verwalten',
                'detailed_description': '''Das Problem: RSS-Feeds manuell zu erstellen und aktuell zu halten ist technisch aufwendig.

Die Workloom-Lösung: BackLoom generiert und verwaltet RSS-Feeds automatisch - für bessere Reichweite!

So funktioniert's:
1️⃣ Content-Quelle verbinden
2️⃣ Feed-Einstellungen konfigurieren
3️⃣ RSS-URL teilen

Dein Content in jedem Feed-Reader!''',
                'key_features': [
                    'Feed-Erstellung',
                    'Automatische Updates',
                    'Verschiedene Formate',
                    'Content-Aggregation',
                    'Feed-Statistiken'
                ]
            },
            'loommarket': {
                'title': 'LoomMarket - Marketing mit Instagram',
                'icon_class': 'bi bi-shop-window',
                'short_description': 'Instagram-Posts in Marketing-Materialien verwandeln',
                'detailed_description': '''Das Problem: Instagram-Content nochmal für Marketing aufzubereiten kostet Zeit.

Die Workloom-Lösung: LoomMarket importiert Instagram-Posts und erstellt daraus Marketing-Materialien - mit KI-Texten und Gravur-Designer!

So funktioniert's:
1️⃣ Instagram-Profil verbinden
2️⃣ Posts auswählen
3️⃣ Marketing-Materialien generieren

Von Instagram zum fertigen Marketing!''',
                'key_features': [
                    'Instagram-Import',
                    'KI-Textgenerierung',
                    'Gravur-Designer',
                    '40+ Schriftarten',
                    'Kampagnen-Verwaltung'
                ]
            },
            'ploom': {
                'title': 'P-Loom - Shopify Produkte mit KI erstellen',
                'icon_class': 'bi bi-box-seam',
                'short_description': 'Produkte mit KI-Beschreibungen direkt in Shopify',
                'detailed_description': '''Das Problem: Shopify-Produkte mit guten Beschreibungen erstellen ist zeitaufwendig.

Die Workloom-Lösung: P-Loom erstellt komplette Produkteinträge mit KI - Titel, Beschreibung, SEO-Meta direkt in Shopify!

So funktioniert's:
1️⃣ Produkt-Details eingeben
2️⃣ KI generiert Texte
3️⃣ Mit einem Klick in Shopify anlegen

Produkte erstellen in Minuten statt Stunden!''',
                'key_features': [
                    'KI-Produktbeschreibungen',
                    'SEO-Meta automatisch',
                    'Direkte Shopify-Sync',
                    'Bulk-Erstellung',
                    'Verschiedene Stile'
                ]
            },
            'keyengine': {
                'title': 'KeyEngine - Keyword-Recherche für SEO',
                'icon_class': 'fas fa-key',
                'short_description': 'Keywords finden und analysieren',
                'detailed_description': '''Das Problem: Die richtigen Keywords zu finden ist die Basis für SEO - aber Tools sind teuer und kompliziert.

Die Workloom-Lösung: KeyEngine liefert Keyword-Ideen mit Suchvolumen und Wettbewerb - einfach und effektiv!

So funktioniert's:
1️⃣ Seed-Keyword eingeben
2️⃣ Keyword-Vorschläge erhalten
3️⃣ Beste Keywords auswählen

Die Grundlage für erfolgreiches SEO!''',
                'key_features': [
                    'Keyword-Recherche',
                    'Suchvolumen-Daten',
                    'Wettbewerbsanalyse',
                    'SERP-Analyse',
                    'Keyword-Clustering'
                ]
            },
            'loomline': {
                'title': 'LoomLine - SEO Aufgaben organisieren',
                'icon_class': 'fas fa-list-alt',
                'short_description': 'SEO-Projekte planen und tracken',
                'detailed_description': '''Das Problem: SEO hat viele Aufgaben - Content, Technik, Backlinks. Den Überblick zu behalten ist schwer.

Die Workloom-Lösung: LoomLine ist dein SEO-Projektmanager - alle Tasks im Blick, mit Keywords und Deadlines!

So funktioniert's:
1️⃣ SEO-Aufgaben erstellen
2️⃣ Keywords zuweisen
3️⃣ Fortschritt tracken

SEO systematisch umsetzen!''',
                'key_features': [
                    'SEO-Aufgabenverwaltung',
                    'Keyword-Zuweisung',
                    'Content-Kalender',
                    'Team-Collaboration',
                    'Deadline-Tracking'
                ]
            },
            'loomtalk': {
                'title': 'LoomTalk - Forum für die Community',
                'icon_class': 'bi bi-chat-dots',
                'short_description': 'Diskutiere mit anderen Workloom-Nutzern',
                'detailed_description': '''Das Problem: Fragen zu Workloom? Ideen teilen? Tipps austauschen? Es fehlt ein zentraler Ort.

Die Workloom-Lösung: LoomTalk ist das Community-Forum - stelle Fragen, teile Wissen, vernetze dich!

So funktioniert's:
1️⃣ Thema erstellen oder durchsuchen
2️⃣ Fragen stellen oder beantworten
3️⃣ Mit @mentions andere einbeziehen

Gemeinsam besser werden!''',
                'key_features': [
                    'Diskussions-Themen',
                    'Kategorien und Tags',
                    'Upvote/Downvote',
                    '@Mentions',
                    'Verschachtelte Antworten'
                ]
            },
            'email_templates': {
                'title': 'Email-Vorlagen - Templates für alle Fälle',
                'icon_class': 'bi bi-envelope-paper',
                'short_description': 'E-Mail-Templates erstellen und verwalten',
                'detailed_description': '''Das Problem: Immer wieder die gleichen E-Mails schreiben kostet Zeit.

Die Workloom-Lösung: Email-Vorlagen speichert deine besten Templates - mit Variablen zum schnellen Anpassen!

So funktioniert's:
1️⃣ Template erstellen mit Platzhaltern
2️⃣ Bei Bedarf aufrufen
3️⃣ Variablen ausfüllen und senden

Professionelle E-Mails in Sekunden!''',
                'key_features': [
                    'Template-Editor',
                    'Variablen-System',
                    'Kategorisierung',
                    'Schnellzugriff',
                    'Team-Sharing'
                ]
            },
        }

        created_count = 0
        updated_count = 0

        for app_name, data in app_descriptions.items():
            obj, created = AppInfo.objects.update_or_create(
                app_name=app_name,
                defaults={
                    'title': data['title'],
                    'icon_class': data['icon_class'],
                    'short_description': data['short_description'],
                    'detailed_description': data['detailed_description'],
                    'key_features': data['key_features'],
                    'is_active': True,
                    'development_status': 'beta',
                    'subscription_requirements': 'Kostenlos in der Beta-Phase',
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Erstellt: {data["title"]}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Aktualisiert: {data["title"]}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Fertig! {created_count} erstellt, {updated_count} aktualisiert.'))

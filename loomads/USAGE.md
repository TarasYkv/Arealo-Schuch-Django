# LoomAds - Werbesystem für Workloom

## Überblick
LoomAds ist ein vollständiges Werbeverwaltungssystem, das exklusiv für Superuser entwickelt wurde. Es ermöglicht die Platzierung und Verwaltung von Werbeanzeigen auf der gesamten Workloom-Plattform.

## Zugriff
- **Dashboard**: `/loomads/` (nur für Superuser)
- **Admin Interface**: `/admin/loomads/` (vollständige Verwaltung)
- **Profilmenü**: Link zu LoomAds im Superuser-Dropdown

## Kernfunktionen

### 1. Kampagnenverwaltung
- Erstellen und verwalten von Werbekampagnen
- Zeitliche Begrenzung und Impression-Limits
- Status-Kontrolle (Entwurf, Aktiv, Pausiert, Abgeschlossen)

### 2. Werbezonen (AdZones)
Verfügbare Zonen-Typen:
- `header` - Header Banner
- `footer` - Footer Banner  
- `sidebar` - Seitenleisten-Anzeigen
- `in_feed` - In-Feed Content
- `modal` - Pop-up/Modal Anzeigen
- `video_preroll` - Video Pre-Roll
- `video_overlay` - Video Overlay
- `content_card` - Content Karten
- `notification` - Benachrichtigungen

### 3. Anzeigenformate
- **Bild-Anzeigen**: Upload von Bilddateien
- **HTML/Rich Content**: Vollständig anpassbare HTML-Anzeigen  
- **Video**: Video-URLs für Bewegtbildwerbung
- **Text**: Einfache Textanzeigen

### 4. Targeting-Optionen
- Gerätezielgruppen (Desktop, Mobile, Tablet)
- Benutzerstatus (Eingeloggt, Anonym)
- App-spezifische Ausrichtung
- URL-basiertes Targeting
- Zeitpläne (Wochentage/Uhrzeiten)

## Template Integration

### Template Tags laden
```django
{% load loomads_tags %}
```

### CSS für Styling einbinden
```django
{% loomads_css %}
```

### Werbezone anzeigen
```django
{% show_ad_zone 'zone_code' %}
{% show_ad_zone 'zone_code' css_class='mb-4' %}
{% show_ad_zone 'zone_code' css_class='my-ad' fallback='<div>Fallback-Inhalt</div>' %}
```

### Modal/Pop-up Anzeige
```django
{% show_ad_modal 'popup_zone' %}
{% show_ad_modal 'popup_zone' delay=5000 %}
```

### Statistiken abrufen
```django
{% ad_stats 30 as stats %}
{{ stats.impressions }} Impressions
{{ stats.clicks }} Klicks
{{ stats.ctr }}% CTR
```

### Platzhalter für Entwicklung
```django
{% ad_zone_placeholder 'zone_code' width=300 height=250 %}
```

## Beispiel-Integration

### Dashboard Template
```django
{% extends 'base.html' %}
{% load loomads_tags %}

{% block content %}
{% loomads_css %}

<!-- Header Banner -->
{% show_ad_zone 'header_main' css_class='mb-4' %}

<div class="row">
    <div class="col-md-9">
        <!-- Hauptinhalt -->
        {% show_ad_zone 'content_infeed' css_class='my-4' %}
    </div>
    <div class="col-md-3">
        <!-- Sidebar Anzeigen -->
        {% show_ad_zone 'sidebar_main' css_class='mb-3' %}
    </div>
</div>

<!-- Footer Banner -->
{% show_ad_zone 'footer_main' css_class='mt-4' %}

<!-- Pop-up für anonyme Nutzer -->
{% show_ad_modal 'popup_welcome' delay=10000 %}
{% endblock %}
```

## Management Commands

### Beispieldaten erstellen
```bash
python manage.py create_sample_ads
```

### Statistiken anzeigen
```bash
python manage.py loomads_stats
python manage.py loomads_stats --detailed
```

## Vordefinierte Werbezonen

Nach der Installation stehen folgende Beispiel-Zonen zur Verfügung:

1. **header_main** (728x90) - Header Banner
2. **sidebar_main** (300x250) - Seitenleisten-Banner
3. **content_infeed** (300x200) - In-Feed Anzeigen
4. **footer_main** (728x90) - Footer Banner
5. **popup_welcome** (400x300) - Willkommens-Pop-up

## API Endpoints

- `GET /loomads/api/ad/<zone_code>/` - Anzeige für Zone abrufen
- `POST /loomads/api/impression/` - Impression tracken
- `POST /loomads/api/click/` - Klick tracken

## Performance & Analytics

Das System trackt automatisch:
- Impressions (Anzeigen-Aufrufe)
- Klicks
- Click-Through-Rate (CTR)
- Zeitstempel und Benutzer-Informationen
- IP-Adressen und User-Agents

## Admin Interface Features

- **Inline-Bearbeitung**: Direkte Bearbeitung von Anzeigen in Kampagnen
- **Vorschau**: Live-Vorschau von HTML-Anzeigen im Admin
- **Bulk-Aktionen**: Massenbearbeitung von Anzeigen
- **Filtering**: Erweiterte Filter- und Suchfunktionen
- **Rich Editor**: WYSIWYG-Editor für HTML-Content

## Sicherheit

- Nur Superuser haben Zugriff auf LoomAds
- UUID-basierte Primary Keys für erhöhte Sicherheit
- XSS-Schutz für benutzerdefinierte HTML-Inhalte
- Tracking-Begrenzungen und Rate-Limiting

## Best Practices

1. **Zonen-Codes**: Verwenden Sie aussagekräftige, eindeutige Codes
2. **Fallbacks**: Definieren Sie immer Fallback-Inhalte für Zonen
3. **Performance**: Begrenzen Sie HTML-Anzeigen auf notwendige Größe
4. **Testing**: Testen Sie Anzeigen in verschiedenen Viewport-Größen
5. **Analytics**: Überwachen Sie regelmäßig die Performance-Metriken

## Troubleshooting

### Anzeigen werden nicht angezeigt
- Prüfen Sie, ob die Zone aktiv ist
- Überprüfen Sie die Kampagnen-Laufzeit
- Kontrollieren Sie Targeting-Einstellungen

### Template Tags funktionieren nicht  
- Stellen Sie sicher, dass `{% load loomads_tags %}` geladen ist
- Überprüfen Sie die Zonen-Codes auf Tippfehler
- Kontrollieren Sie die Template-Syntax

### Performance-Probleme
- Begrenzen Sie die Anzahl der Zonen pro Seite
- Optimieren Sie HTML-Content in Anzeigen
- Nutzen Sie Browser-Caching für Bilder

## Weiterentwicklung

Das System ist modular aufgebaut und kann erweitert werden um:
- Programmatic Advertising
- A/B Testing
- Erweiterte Targeting-Optionen
- Integration mit externen Ad-Servern
- Automatisierte Optimierung
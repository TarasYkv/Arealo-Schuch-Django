# App-Freigabe System

## Übersicht

Das App-Freigabe System ermöglicht es Superusern und Benutzern mit entsprechenden Berechtigung, den Zugriff auf verschiedene Apps und Funktionen der Plattform zu steuern.

## Neue Funktionen

### 1. App-Freigabe Tab in Firmeninfo

- **URL**: `http://127.0.0.1:8000/accounts/firmeninfo/?tab=app_permissions`
- **Berechtigung**: Nur Superuser oder Benutzer mit `can_manage_app_permissions = True`
- **Funktion**: Verwalten der App-Berechtigungen für alle verfügbaren Apps

### 2. Verfügbare Apps/Funktionen

**Hauptkategorien:**
- Schulungen
- Shopify
- Bilder
- ToDos
- Chat
- Organisation

**Shopify Unterkategorien:**
- Produkte
- Blogs
- SEO Dashboard
- Verkaufszahlen
- SEO-Optimierung
- Alt-Text Manager

**Organisation Unterkategorien:**
- Notizen
- Termine
- Ideenboards
- Ausstehende Terminanfragen

### 3. Zugriffsebenen

- **Gesperrt**: Niemand hat Zugriff
- **Nicht angemeldete Besucher**: Öffentlicher Zugriff für alle
- **Angemeldete Nutzer**: Nur für eingeloggte Benutzer
- **Ausgewählte Nutzer**: Nur für spezifisch ausgewählte Benutzer

### 4. Erweiterte Optionen

- **Im Frontend ausblenden**: App wird in Navigation/UI nicht angezeigt, auch wenn technisch zugänglich
- **Superuser Bypass**: Superuser haben unabhängig von den Einstellungen vollen Zugriff (Standard: aktiviert)

## Technische Implementierung

### Models

#### CustomUser Erweiterung
```python
can_manage_app_permissions = models.BooleanField(default=False)
```

#### AppPermission Model
```python
class AppPermission(models.Model):
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, unique=True)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES)
    selected_users = models.ManyToManyField(CustomUser, blank=True)
    is_active = models.BooleanField(default=True)
```

### Verwendung in Views

#### Decorator
```python
from accounts.decorators import require_app_permission

@require_app_permission('schulungen')
def schulungen_view(request):
    # View Code
    pass
```

#### Class-Based Views
```python
from accounts.decorators import AppPermissionMixin

class SchulungenView(AppPermissionMixin, ListView):
    app_name = 'schulungen'
    model = Schulung
```

#### Manuelle Prüfung
```python
from accounts.models import AppPermission

def my_view(request):
    if AppPermission.user_has_access('schulungen', request.user):
        # User hat Zugriff
        pass
```

### Verwendung in Templates

#### Template Tags laden
```html
{% load app_permissions %}
```

#### Filter verwenden
```html
<!-- Funktionaler Zugriff prüfen -->
{% if user|has_app_permission:"schulungen" %}
    <a href="{% url 'schulungen:index' %}">Schulungen</a>
{% endif %}

<!-- Frontend-Sichtbarkeit prüfen -->
{% if user|can_see_app_in_frontend:"schulungen" %}
    <a href="{% url 'schulungen:index' %}">Schulungen</a>
{% endif %}
```

#### Navigation Links
```html
<!-- Automatische Frontend-Sichtbarkeitsprüfung -->
{% app_nav_link "schulungen" "schulungen:index" "bi-mortarboard" "Schulungen" user %}

<!-- Nur funktionalen Zugriff prüfen -->
{% app_nav_link "schulungen" "schulungen:index" "bi-mortarboard" "Schulungen" user False %}
```

#### Simple Tag
```html
{% check_app_access "schulungen" user as can_access %}
{% if can_access %}
    <!-- Inhalt anzeigen -->
{% endif %}
```

## Admin-Interface

Das AppPermission Model ist im Django Admin verfügbar:
- **URL**: `/admin/accounts/apppermission/`
- **Funktionen**: CRUD-Operationen für App-Berechtigungen
- **Filter**: Nach Zugriffsebene, Aktivitätsstatus und App-Name

## Migration

Zum Aktivieren der neuen Funktionalität:

1. Migration ausführen:
```bash
python manage.py migrate accounts
```

2. Berechtigung für Benutzer setzen:
```python
# Im Django Admin oder Shell
user = CustomUser.objects.get(username='admin')
user.can_manage_app_permissions = True
user.save()
```

3. Standard-Berechtigungen erstellen (automatisch beim ersten Laden des Formulars)

## Sicherheitsaspekte

1. **Berechtigung erforderlich**: Nur Superuser oder Benutzer mit `can_manage_app_permissions` können das Tab sehen
2. **Standardmäßig gesperrt**: Neue Apps sind standardmäßig für alle gesperrt
3. **Granulare Kontrolle**: Verschiedene Zugriffsebenen für unterschiedliche Anforderungen
4. **Template-Integration**: Einfache Verwendung in Templates für UI-Steuerung

## Beispiel-Workflows

### App für alle angemeldeten Nutzer freigeben
1. Zu Firmeninfo → App-Freigabe Tab navigieren
2. App auswählen (z.B. "Schulungen")
3. Zugriffsebene auf "Angemeldete Nutzer" setzen
4. Speichern

### App nur für ausgewählte Nutzer freigeben
1. Zu Firmeninfo → App-Freigabe Tab navigieren
2. App auswählen (z.B. "Shopify - Verkaufszahlen")
3. Zugriffsebene auf "Ausgewählte Nutzer" setzen
4. Gewünschte Nutzer aus der Liste auswählen
5. Speichern

### Navigation in Templates steuern
```html
{% load app_permissions %}

<nav>
    {% if user|has_app_permission:"schulungen" %}
        <a href="{% url 'schulungen:index' %}">Schulungen</a>
    {% endif %}
    
    {% if user|has_app_permission:"shopify_produkte" %}
        <a href="{% url 'shopify:products' %}">Produkte</a>
    {% endif %}
</nav>
```

## Fehlerbehebung

### Häufige Probleme

1. **Tab nicht sichtbar**: Prüfen ob `can_manage_app_permissions = True` oder Superuser-Status
2. **Formular lädt nicht**: Migration `0011_customuser_can_manage_app_permissions_apppermission` ausführen
3. **Template Tags funktionieren nicht**: `{% load app_permissions %}` am Anfang des Templates hinzufügen

### Debug-Kommandos

```python
# Django Shell
from accounts.models import AppPermission, CustomUser

# Alle Berechtigungen anzeigen
AppPermission.objects.all()

# Prüfen ob User Zugriff hat
user = CustomUser.objects.get(username='testuser')
AppPermission.user_has_access('schulungen', user)

# Berechtigung erstellen
perm = AppPermission.objects.create(
    app_name='schulungen',
    access_level='authenticated'
)
```
# Email-Vorlagen App - Setup Anleitung

## 📧 Überblick

Die Email-Vorlagen App ermöglicht es Superusern, professionelle Email-Vorlagen zu erstellen und über Zoho Mail zu versenden. Die App ist speziell für die Gestaltung von Bestell-Emails und anderen automatisierten Nachrichten konzipiert.

## 🚀 Schnellstart

### 1. App-Zugang (Nur für Superuser)

Die Email-Vorlagen App ist nur für **Superuser** zugänglich:

**Navigation:**
- 📍 **Hauptnavigation**: "Email-Vorlagen" (mit Icon)
- 📍 **Benutzer-Dropdown**: "Email-Vorlagen" im Profil-Bereich

**URL:** `https://workloom.de/email-templates/`

### 2. Erste Schritte

1. **Als Superuser anmelden**
2. **Email-Vorlagen Dashboard aufrufen**
3. **Erste Zoho-Verbindung einrichten**
4. **Erste Email-Vorlage erstellen**

## 🔗 Zoho Mail Verbindung einrichten

### Schritt 1: Zoho Developer Account vorbereiten

Benötigt werden die gleichen Zoho-Credentials wie für die Mail-App:

```bash
# Aus bestehender .env oder Zoho Console
ZOHO_CLIENT_ID=1000.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Schritt 2: Neue Verbindung erstellen

1. **Email-Vorlagen Dashboard** aufrufen
2. **"Neue Verbindung"** klicken
3. **Verbindungsdaten eingeben:**

```
Name: Hauptverbindung Workloom
Email-Adresse: kontakt@workloom.de
Region: EU
Client ID: [Aus Zoho Console]
Client Secret: [Aus Zoho Console]
Redirect URI: https://workloom.de/email-templates/oauth/callback/
```

### Schritt 3: OAuth2-Autorisierung

1. **"Speichern"** klicken
2. **"Verbindung konfigurieren"** (Auth-URL verwenden)
3. **Bei Zoho anmelden** (kontakt@workloom.de)
4. **Berechtigung erteilen** für Email-Senden
5. **Automatische Rückleitung** zur App

### Schritt 4: Verbindung testen

1. **"Verbindung testen"** klicken
2. ✅ **Erfolgreich**: Grüner "Konfiguriert"-Status
3. ❌ **Fehler**: Rote Fehlermeldung im Dashboard

## 📧 Email-Vorlagen erstellen

### Standard-Kategorien

Die App enthält bereits 5 vordefinierte Kategorien:

- 🛒 **Bestellungen** - Bestellbestätigungen, Versand, etc.
- 📰 **Newsletter** - Marketing und Newsletter
- 👥 **Benutzerverwaltung** - Registrierung, Passwort-Reset
- 🎧 **Support** - Kundensupport und Hilfe
- ✉️ **Allgemein** - Sonstige Email-Vorlagen

### Neue Vorlage erstellen

1. **"Neue Vorlage"** im Dashboard
2. **Grundeinstellungen:**
   ```
   Name: Bestellbestätigung Standard
   Kategorie: Bestellungen
   Typ: Bestellbestätigung
   ```

3. **Email-Inhalt:**
   ```
   Betreff: Ihre Bestellung {{order_number}} wurde bestätigt
   
   HTML-Inhalt:
   <h1>Vielen Dank für Ihre Bestellung!</h1>
   <p>Hallo {{customer_name}},</p>
   <p>Ihre Bestellung <strong>{{order_number}}</strong> wurde erfolgreich aufgenommen.</p>
   
   <h2>Bestelldetails:</h2>
   <ul>
   {{#order_items}}
     <li>{{name}} - {{quantity}}x {{price}}€</li>
   {{/order_items}}
   </ul>
   
   <p><strong>Gesamtsumme: {{total_amount}}€</strong></p>
   
   <p>Mit freundlichen Grüßen,<br>
   Ihr Workloom Team</p>
   ```

4. **Template-Variablen definieren:**
   ```json
   {
     "customer_name": "Name des Kunden",
     "order_number": "Bestellnummer",
     "order_items": "Liste der bestellten Artikel",
     "total_amount": "Gesamtbetrag der Bestellung"
   }
   ```

## 🧪 Testen der Email-Vorlagen

### Live-Vorschau

1. **Vorlage öffnen**
2. **"Vorschau"** klicken
3. **Test-Daten eingeben:**
   ```json
   {
     "customer_name": "Max Mustermann",
     "order_number": "WL-2025-001",
     "order_items": [
       {"name": "Produkt A", "quantity": 2, "price": 19.99}
     ],
     "total_amount": 43.98
   }
   ```

### Test-Email senden

1. **"Test-Email senden"** im Dashboard
2. **Einstellungen:**
   ```
   Vorlage: Bestellbestätigung Standard
   Verbindung: Hauptverbindung Workloom
   Empfänger: ihre-test@email.de
   Test-Daten: [Wie oben]
   ```

3. **"Senden"** klicken
4. ✅ **Erfolgreich**: Grüne Bestätigung
5. ❌ **Fehler**: Rote Fehlermeldung mit Details

## 🔧 Administration

### Django Admin Zugang

Vollständige Verwaltung über Django Admin:
- **URL**: `/admin/email_templates/`
- **Modelle**: Verbindungen, Vorlagen, Kategorien, Versandlogs

### Management Commands

```bash
# App-Berechtigung einrichten
python manage.py setup_email_templates_permission

# Standard-Kategorien erstellen
python manage.py setup_default_email_categories
```

## 🚨 Troubleshooting

### Häufige Probleme

**1. "Zugriff verweigert"**
- ❌ Benutzer ist kein Superuser
- ✅ Superuser-Status im Admin prüfen

**2. "OAuth-Fehler"**
- ❌ Client ID/Secret falsch
- ❌ Redirect URI stimmt nicht überein
- ✅ Zoho Console Einstellungen prüfen

**3. "Email-Versand fehlgeschlagen"**
- ❌ Verbindung nicht konfiguriert
- ❌ Token abgelaufen
- ✅ Verbindung neu autorisieren

**4. "Template-Rendering-Fehler"**
- ❌ Ungültige Template-Syntax
- ❌ Fehlende Variablen
- ✅ Test-Daten vollständig eingeben

### Debug-Informationen

**Logs prüfen:**
```bash
# Django Development Server
python manage.py runserver --verbosity=2

# Produktions-Logs
tail -f /var/log/django/email_templates.log
```

**Admin-Bereiche:**
- `/admin/email_templates/zohomailserverconnection/` - Verbindungen
- `/admin/email_templates/emailtemplate/` - Vorlagen
- `/admin/email_templates/emailsendlog/` - Versandprotokolle

## 📋 Features im Überblick

### ✅ Implementiert

- 🔗 **Zoho Mail OAuth2-Integration**
- 📧 **Email-Vorlagen mit HTML/Text**
- 🏷️ **Kategorien-System**
- 👀 **Live-Vorschau mit Test-Daten**
- 📊 **Dashboard mit Statistiken**
- 🧪 **Test-Email-Funktionalität**
- 📚 **Versionsverwaltung der Vorlagen**
- 🔒 **Superuser-only Zugriff**
- 📝 **Vollständiges Admin-Interface**

### 🔄 Geplante Erweiterungen

- 🎨 **WYSIWYG-Editor** (Rich-Text)
- 📱 **Email-Designer** (Drag & Drop)
- 🔄 **Automatische Sendungen** (Trigger-basiert)
- 📈 **Erweiterte Statistiken** (Öffnungsraten, etc.)
- 🌐 **Multi-Sprach-Support**

## 🎯 Anwendungsfälle

### Typische Workflows

**1. Bestellbestätigungen:**
```python
# Automatischer Versand nach Bestellung
from email_templates.services import EmailNotificationService

EmailNotificationService.send_order_confirmation(
    order_data={
        'customer_name': 'Max Mustermann',
        'order_number': 'WL-2025-001',
        # ...
    },
    recipient_email='kunde@example.com'
)
```

**2. Willkommens-Emails:**
```python
# Neuer Benutzer registriert
EmailNotificationService.send_welcome_email(
    user_data={
        'username': 'max.mustermann',
        'first_name': 'Max',
        # ...
    },
    recipient_email='max@example.com'
)
```

**3. Newsletter-Versand:**
```python
# Über Template-Service
from email_templates.services import EmailTemplateService

EmailTemplateService.send_template_email(
    template=newsletter_template,
    connection=zoho_connection,
    recipient_email='subscriber@example.com',
    context_data={'news': news_items}
)
```

## 📞 Support

Bei Problemen oder Fragen:

1. **Debug-Logs** prüfen
2. **Admin-Interface** verwenden
3. **Test-Verbindungen** durchführen
4. **Management Commands** ausführen

---

*Erstellt: Januar 2025*  
*Version: 1.0*  
*Status: Produktionsbereit* ✅
# 📧 E-Mail-Konfiguration für Workloom

## Problem
Neue Benutzer erhalten keine Bestätigungs-E-Mails, da das E-Mail-System nicht konfiguriert ist.

## Lösung
Das Double-Opt-In System ist vollständig implementiert. Sie müssen nur noch die E-Mail-Credentials konfigurieren.

## ✅ Bereits implementiert:
- ✅ Double-Opt-In System mit E-Mail-Verifikation
- ✅ Professionelle E-Mail-Templates (HTML + Text)
- ✅ Sichere Token-Generierung (24h Gültigkeit)
- ✅ Automatische Benutzer-Aktivierung nach Verifikation
- ✅ E-Mail erneut senden Funktion (Rate-Limited)
- ✅ Benutzerfreundliche UI für alle Schritte

## 🔧 Konfiguration erforderlich:

### 1. E-Mail-Credentials in .env Datei setzen

Bearbeiten Sie die `.env` Datei im Projekt-Root und setzen Sie:

```bash
# Für Gmail (empfohlen)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=kontakt@workloom.de
EMAIL_HOST_PASSWORD=ihr-gmail-app-passwort

# Für Outlook/Office365
# EMAIL_HOST=smtp.office365.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=kontakt@workloom.de
# EMAIL_HOST_PASSWORD=ihr-outlook-passwort

# Für eigenen Mail-Server
# EMAIL_HOST=mail.ihr-domain.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=kontakt@workloom.de
# EMAIL_HOST_PASSWORD=ihr-email-passwort
```

### 2. Gmail App-Passwort erstellen (falls Gmail verwendet wird)

1. **Google-Konto öffnen**: https://myaccount.google.com/
2. **Sicherheit** → **2-Faktor-Authentifizierung** aktivieren
3. **App-Passwörter** → **App auswählen**: "Mail"
4. **Gerät auswählen**: "Sonstiges" → "Workloom"
5. **Generiertes 16-stelliges Passwort** in .env eintragen

### 3. Konfiguration testen

```bash
# E-Mail-Konfiguration prüfen
python manage.py test_email_config

# Test-E-Mail senden
python manage.py test_email_config --send-test --to ihre-email@beispiel.de
```

### 4. System neu starten

Nach Änderung der .env Datei:
```bash
# Django Development Server neu starten
python manage.py runserver
```

## 🚀 Funktionsweise nach Konfiguration:

### Neue Benutzer-Registrierung:
1. Benutzer füllt Registrierungsformular aus
2. **Benutzer wird als inaktiv erstellt**
3. **Automatische E-Mail-Versendung** mit Bestätigungslink
4. Benutzer sieht "Registrierung erfolgreich" Seite
5. Benutzer klickt auf Link in E-Mail
6. **Automatische Aktivierung + Login**

### E-Mail-Inhalt:
- **Professionelles Workloom-Design**
- **HTML + Text Version**
- **Sichere 24h-gültige Links**
- **Feature-Übersicht**
- **Alternative Link falls Button nicht funktioniert**

### Sicherheitsfeatures:
- ✅ Sichere Token-Generierung mit `secrets`
- ✅ 24-Stunden Link-Gültigkeit
- ✅ Rate-Limiting (5min zwischen E-Mails)
- ✅ Token wird nach Verwendung gelöscht
- ✅ Login-Sperre für unverifizierte Benutzer

## 🔍 Troubleshooting:

### E-Mails kommen nicht an:
```bash
# 1. Konfiguration prüfen
python manage.py test_email_config

# 2. Test-E-Mail senden
python manage.py test_email_config --send-test --to ihre-email@beispiel.de

# 3. Django-Logs prüfen
tail -f logs/django.log  # falls Log-Datei existiert
```

### Häufige Probleme:
- **Gmail**: App-Passwort statt normales Passwort verwenden
- **Outlook**: Moderne Authentifizierung aktiviert?
- **Spam-Ordner**: E-Mails landen oft im Spam
- **Firewall**: Port 587 blockiert?

## 📊 Status prüfen:

```bash
# Benutzer-Status anzeigen
python manage.py shell -c "
from accounts.models import CustomUser
users = CustomUser.objects.all()
for user in users:
    print(f'{user.username}: aktiv={user.is_active}, verifiziert={user.email_verified}')
"

# Bestehende Benutzer als verifiziert markieren
python manage.py update_existing_users_verification --verify-all --activate-all
```

## ✨ Nach erfolgreicher Konfiguration:

Das System funktioniert vollautomatisch:
- **Neue Registrierungen** erhalten sofort Bestätigungs-E-Mails
- **Benutzer können sich nicht anmelden** bis E-Mail bestätigt
- **Professionelle Willkommens-E-Mails** mit Workloom-Branding
- **Automatische Aktivierung** nach Klick auf Bestätigungslink

---

**💡 Tipp**: Starten Sie mit Gmail - das ist am einfachsten zu konfigurieren und sehr zuverlässig.
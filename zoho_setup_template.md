# Zoho Mail OAuth2 Setup Template

## 1. Nach der App-Erstellung in Zoho Console

Trage die echten Werte aus der Zoho Developer Console hier ein:

```bash
# Zoho Mail Configuration - ECHTE WERTE HIER EINTRAGEN
ZOHO_CLIENT_ID=1000.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ZOHO_REDIRECT_URI=http://localhost:8000/mail/auth/callback/
```

## 2. Für Production (später)

```bash
# Production URLs
ZOHO_REDIRECT_URI=https://workloom.de/mail/auth/callback/
```

## 3. Testen der Konfiguration

Nach dem Eintragen der echten Credentials:

1. Server starten:
   ```bash
   python manage.py runserver
   ```

2. Mail App aufrufen:
   ```
   http://localhost:8000/mail/
   ```

3. OAuth2 Flow testen:
   - Klick auf "Connect Email Account"
   - Weiterleitung zu Zoho
   - Berechtigung erteilen
   - Zurück zur App

## 4. Erwartetes Verhalten

✅ **Erfolgreich:**
- Weiterleitung zu Zoho funktioniert
- Login mit kontakt@workloom.de
- Berechtigung erteilen
- Rückleitung zur App
- Folders werden synchronisiert
- Dashboard zeigt Email-Account

❌ **Bei Fehlern:**
- Prüfe Client ID/Secret
- Prüfe Redirect URI (exakt wie in Zoho Console)
- Prüfe Django Logs für Details

## 5. Debug-Kommandos

```bash
# Django Logs anzeigen
python manage.py runserver --verbosity=2

# Direkt im Admin prüfen
http://localhost:8000/admin/mail_app/emailaccount/
```

## 6. Troubleshooting

**Häufige Fehler:**
- `Invalid client_id`: Client ID falsch eingetragen
- `Redirect URI mismatch`: URI in Zoho Console anders als in .env
- `Invalid scope`: Scopes nicht korrekt konfiguriert

## 7. Nach erfolgreichem Setup

Die App kann dann:
- Emails von kontakt@workloom.de abrufen
- Emails senden
- Ordner synchronisieren
- Attachments verwalten

## 8. Nächste Schritte

Nach erfolgreichem OAuth2-Setup:
- Phase 2: Core Features entwickeln
- Templates erstellen
- Frontend-Interface implementieren
- Email-Synchronisation testen
# Workloom.de Setup für Mail App

## OAuth Redirect-URI Problem beheben

### 1. Environment Variables konfigurieren

Auf Ihrem Server (PythonAnywhere oder eigenem Server) setzen Sie folgende Environment Variables:

```bash
# Zoho OAuth Settings
ZOHO_CLIENT_ID=your_client_id_here
ZOHO_CLIENT_SECRET=your_client_secret_here
ZOHO_REDIRECT_URI=https://workloom.de/mail/auth/callback/
ZOHO_ACCOUNT_ID=your_account_id_here

# Django Settings
SECRET_KEY=your_secret_key_here
DEBUG=False
ALLOWED_HOSTS=workloom.de,www.workloom.de

# Optional: Database encryption key
DB_ENCRYPTION_KEY=your_encryption_key_here
```

**WICHTIG**: Die Redirect-URI muss exakt `https://workloom.de/mail/auth/callback/` sein!

### 2. Zoho API Console konfigurieren

1. Gehen Sie zu https://api-console.zoho.com/
2. Wählen Sie Ihre App aus
3. Gehen Sie zu "Client Details" oder "Settings"
4. Fügen Sie die Redirect URI hinzu:
   ```
   https://workloom.de/mail/auth/callback/
   ```
5. Speichern Sie die Änderungen

### 3. Settings.py für Workloom.de anpassen

Stellen Sie sicher, dass Ihre `settings.py` folgende Konfiguration hat:

```python
# Für Workloom.de
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'workloom.de',
    'www.workloom.de',
]

# HTTPS für Production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
```

### 4. Static Files sammeln

Führen Sie auf PythonAnywhere aus:

```bash
python manage.py collectstatic
```

### 5. Datenbank migrieren

```bash
python manage.py migrate
```

### 6. Fehlerdiagnose

Falls immer noch Probleme auftreten:

1. **Überprüfen Sie die exakte URL**: 
   - Öffnen Sie https://workloom.de/mail/auth/callback/ im Browser
   - Sie sollten einen 405 oder 400 Error sehen (das ist normal)

2. **Debug-Modus temporär aktivieren**:
   ```python
   # In views.py oauth_authorize function
   print(f"Redirect URI being used: {redirect_uri}")
   ```

3. **Überprüfen Sie die Logs**:
   - PythonAnywhere → Files → Log files → Error log

### 7. Alternative: Dynamische Redirect-URI

Falls Sie die Redirect-URI nicht fest konfigurieren möchten, können Sie sie dynamisch generieren lassen. Die App macht das bereits in `accounts/views.py`:

```python
redirect_uri = request.build_absolute_uri('/mail/auth/callback/')
```

Dies funktioniert automatisch für jede Domain.

### 8. Häufige Fehler

1. **Trailing Slash vergessen**: Die URI muss mit `/` enden
2. **HTTP statt HTTPS**: PythonAnywhere verwendet HTTPS
3. **Falscher Username**: Überprüfen Sie Ihren exakten PythonAnywhere-Benutzernamen
4. **Alte Redirect-URIs**: Entfernen Sie alte localhost-URIs aus Zoho

### 9. Test der Konfiguration

1. Gehen Sie zu https://workloom.de/mail/
2. Klicken Sie auf "Email-Account verbinden"
3. Sie sollten zur Zoho-Login-Seite weitergeleitet werden
4. Nach der Anmeldung sollten Sie zurück zu Ihrer App geleitet werden

## Troubleshooting

### Error: "Invalid redirect URI"
- Überprüfen Sie die exakte Schreibweise in Zoho und PythonAnywhere
- Stellen Sie sicher, dass beide URIs identisch sind (inkl. Trailing Slash)

### Error: "redirect_uri_mismatch"
- Die URI in der OAuth-Anfrage stimmt nicht mit der konfigurierten überein
- Überprüfen Sie die Environment Variable `ZOHO_REDIRECT_URI`

### Weitere Hilfe
- PythonAnywhere Forums: https://www.pythonanywhere.com/forums/
- Zoho OAuth Documentation: https://www.zoho.com/mail/help/api/
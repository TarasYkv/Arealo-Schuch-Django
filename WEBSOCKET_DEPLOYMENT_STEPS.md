# 🚀 WebSocket Video Chat - Inbetriebnahme auf PythonAnywhere

## Voraussetzung
✅ Django Webseite läuft bereits auf PythonAnywhere  
✅ Bezahlte PythonAnywhere Version (WebSocket Support)

## 📋 Schritt-für-Schritt Anleitung

### 1. Code aktualisieren
```bash
# Auf PythonAnywhere im Terminal
cd ~/Arealo-Schuch
git pull origin main
```

### 2. WebSocket Dependencies installieren
```bash
# Virtual Environment aktivieren
source venv/bin/activate

# WebSocket Packages installieren
pip install channels==4.0.0 channels-redis==4.2.0 daphne==4.0.0
```

### 3. Production Settings erstellen
```bash
# Settings Datei erstellen
cp Schuch/settings_production.py.template Schuch/settings_production.py

# Bearbeiten (wichtige Werte setzen):
nano Schuch/settings_production.py
```

**In settings_production.py ändern:**
```python
# Sicheren Secret Key setzen
SECRET_KEY = 'ihr-production-secret-key-hier'

# Ihre Domain
ALLOWED_HOSTS = [
    'workloom.de',
    'www.workloom.de',
    'tarasyuzkiv.pythonanywhere.com',
]
```

### 4. ASGI File auf PythonAnywhere hochladen
```bash
# ASGI Datei kopieren
cp pythonanywhere_asgi.py /var/www/tarasyuzkiv_pythonanywhere_com_asgi.py
```

### 5. Web App auf ASGI umstellen

**Im PythonAnywhere Web Tab:**
1. Gehen Sie zu Ihrem **Web Tab**
2. Scrollen Sie zu **Code**
3. Ändern Sie **WSGI configuration file** zu **ASGI configuration file**
4. Setzen Sie den Pfad: `/var/www/tarasyuzkiv_pythonanywhere_com_asgi.py`

### 6. Database Migration (falls nötig)
```bash
# Nur falls neue Models vorhanden
python manage.py migrate --settings=Schuch.settings_production
```

### 7. Static Files aktualisieren
```bash
python manage.py collectstatic --settings=Schuch.settings_production --noinput
```

### 8. Web App neu starten
**Im PythonAnywhere Web Tab:**
- Klicken Sie den grünen **"Reload"** Button

### 9. HTTPS aktivieren (für Video Calls erforderlich)
**Im PythonAnywhere Web Tab:**
1. Scrollen Sie zu **HTTPS**
2. Aktivieren Sie **"Force HTTPS"**
3. Aktivieren Sie **Let's Encrypt** für workloom.de

### 10. Funktionalität testen

**A) WebSocket Verbindung testen:**
- Öffnen Sie https://workloom.de/chat/
- Browser Console öffnen (F12)
- Eingeben: 
```javascript
const ws = new WebSocket('wss://workloom.de/ws/call/1/');
ws.onopen = () => console.log('✅ WebSocket OK');
```

**B) Video Call testen:**
1. Zwei Browser Tabs öffnen
2. Verschiedene Accounts einloggen
3. Chat Room öffnen
4. Video Call starten
5. Kamera/Mikrofon Permissions erlauben

## 🚨 Fehlerbehandlung

### Problem: WebSocket Verbindung fehlgeschlagen
```bash
# Logs prüfen
tail -f /var/log/tarasyuzkiv.pythonanywhere.com.error.log
```

### Problem: Video Call funktioniert nicht
- ✅ HTTPS aktiviert?
- ✅ Browser Permissions erteilt?
- ✅ ASGI File korrekt gesetzt?

### Problem: "Module not found"
```bash
# Dependencies erneut installieren
pip install -r requirements_production.txt
```

## ✅ Erfolgreich wenn:
- [ ] WebSocket Verbindung erfolgreich
- [ ] Video Call startet
- [ ] Audio/Video übertragen wird
- [ ] Beide Teilnehmer sich sehen/hören

## 🎯 Das war's!
Ihre Video Chat Funktionalität ist jetzt auf workloom.de aktiv!
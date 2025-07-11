# 🚀 Deployment Guide für workloom.de auf PythonAnywhere

## 📋 Übersicht
Diese Anleitung führt Sie durch das komplette Deployment der Video Chat Anwendung auf PythonAnywhere mit der Domain workloom.de.

## ✅ Voraussetzungen
- ✅ Bezahlte PythonAnywhere Version (WebSocket Support)
- ✅ Domain workloom.de bereits konfiguriert
- ✅ GitHub Repository bereit
- ✅ Alle Dateien vorbereitet

## 🔧 1. Vorbereitung auf PythonAnywhere

### A) GitHub Repository klonen
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/Arealo-Schuch.git
cd Arealo-Schuch
```

### B) Virtual Environment erstellen
```bash
python3.10 -m venv venv
source venv/bin/activate
```

### C) Dependencies installieren
```bash
pip install -r requirements_production.txt
```

## ⚙️ 2. PythonAnywhere Web App Konfiguration

### A) Web Tab Einstellungen:
1. **Domain**: `workloom.de`
2. **Python Version**: `3.10`
3. **Source Code**: `/home/tarasyuzkiv/Arealo-Schuch`
4. **Working Directory**: `/home/tarasyuzkiv/Arealo-Schuch`
5. **ASGI File**: `/var/www/tarasyuzkiv_pythonanywhere_com_asgi.py`

### B) ASGI File konfigurieren:
Kopieren Sie den Inhalt von `pythonanywhere_asgi.py` nach `/var/www/tarasyuzkiv_pythonanywhere_com_asgi.py`

### C) Production Settings erstellen:
```bash
# Kopieren Sie die vorbereitete Datei
cp Schuch/settings_production.py.template Schuch/settings_production.py

# Bearbeiten Sie die Datei und setzen Sie sichere Werte:
nano Schuch/settings_production.py
```

**Wichtige Änderungen in settings_production.py:**
```python
# Sicheren Secret Key generieren
SECRET_KEY = 'ihr-sicherer-production-key-hier'

# Domain konfigurieren
ALLOWED_HOSTS = [
    'workloom.de',
    'www.workloom.de',
    'tarasyuzkiv.pythonanywhere.com',
]
```

## 🗄️ 3. Database Setup

```bash
# In der virtuellen Umgebung
python manage.py migrate --settings=Schuch.settings_production
python manage.py collectstatic --settings=Schuch.settings_production --noinput
python manage.py createsuperuser --settings=Schuch.settings_production
```

## 🔒 4. SSL/HTTPS Konfiguration

### A) PythonAnywhere HTTPS aktivieren:
1. Gehen Sie zum **Web Tab**
2. Scrollen Sie zu **HTTPS**
3. Aktivieren Sie **Force HTTPS**

### B) SSL-Zertifikat für workloom.de:
- PythonAnywhere bietet automatische Let's Encrypt Zertifikate
- Aktivieren Sie diese für workloom.de

## 🌐 5. Domain Konfiguration

### A) DNS Settings (bei Ihrem Domain Provider):
```
Typ    Name    Wert
A      @       YOUR.PYTHONANYWHERE.IP
CNAME  www     workloom.de
```

### B) PythonAnywhere Domain Setup:
1. **Web Tab** → **Add new web app**
2. **Domain**: `workloom.de`
3. **Same as existing app**: Ja, verlinken mit bestehender App

## 🧪 6. Testing

### A) Basic Django Test:
```bash
# Test Settings
python manage.py check --settings=Schuch.settings_production

# Test Database
python manage.py shell --settings=Schuch.settings_production
```

### B) WebSocket Test:
```javascript
// Browser Console auf https://workloom.de
const ws = new WebSocket('wss://workloom.de/ws/chat/1/');
ws.onopen = () => console.log('✅ WebSocket connected!');
ws.onerror = (error) => console.error('❌ WebSocket error:', error);
```

### C) Video Call Test:
1. Zwei Browser öffnen (verschiedene Accounts)
2. Chat öffnen
3. Video Call starten
4. Permissions für Kamera/Mikrofon erteilen

## 🚨 7. Troubleshooting

### A) WebSocket Verbindungsfehler:
```bash
# Logs prüfen
tail -f /var/log/tarasyuzkiv.pythonanywhere.com.error.log
tail -f /home/tarasyuzkiv/Arealo-Schuch/django_errors.log
```

### B) Video Call funktioniert nicht:
- ✅ HTTPS aktiv?
- ✅ Browser Permissions erteilt?
- ✅ Firewall/Corporate Network?

### C) Static Files werden nicht geladen:
```bash
python manage.py collectstatic --settings=Schuch.settings_production --clear
```

## 📊 8. Performance Monitoring

### A) Log Files überwachen:
```bash
# Django Errors
tail -f /home/tarasyuzkiv/Arealo-Schuch/django_errors.log

# PythonAnywhere Logs
tail -f /var/log/tarasyuzkiv.pythonanywhere.com.error.log
```

### B) WebSocket Connections monitoren:
- PythonAnywhere Dashboard → **Tasks**
- Überprüfen Sie CPU/Memory Usage

## 🔄 9. Updates und Wartung

### A) Code Updates via Git:
```bash
cd ~/Arealo-Schuch
git pull origin main
source venv/bin/activate
pip install -r requirements_production.txt
python manage.py migrate --settings=Schuch.settings_production
python manage.py collectstatic --settings=Schuch.settings_production --noinput

# Web App neu starten
# Web Tab → Green "Reload" Button
```

### B) Database Backup:
```bash
# SQLite Backup
cp /home/tarasyuzkiv/Arealo-Schuch/db.sqlite3 /home/tarasyuzkiv/backups/db_$(date +%Y%m%d).sqlite3
```

## ✅ 10. Go-Live Checklist

- [ ] GitHub Repository aktuell
- [ ] Production Settings konfiguriert
- [ ] ASGI File hochgeladen
- [ ] Dependencies installiert
- [ ] Database migriert
- [ ] Static Files gesammelt
- [ ] Superuser erstellt
- [ ] HTTPS aktiviert
- [ ] Domain konfiguriert
- [ ] WebSocket Verbindung getestet
- [ ] Video Call getestet
- [ ] Error Logs überwacht

## 🎯 11. Post-Deployment

### A) Benutzer informieren:
- Video Calls benötigen HTTPS
- Browser Permissions erforderlich
- Kompatible Browser (Chrome, Firefox, Safari)

### B) Monitoring Setup:
- Täglich Error Logs prüfen
- Performance überwachen
- User Feedback sammeln

## 📞 Support

Bei Problemen:
1. **Logs prüfen** (siehe Troubleshooting)
2. **PythonAnywhere Help** → **Send feedback**
3. **Django Debug** aktivieren (temporär)

---

**🚀 Ihre Video Chat Anwendung ist bereit für workloom.de!**
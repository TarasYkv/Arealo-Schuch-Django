# PythonAnywhere Deployment Guide für Video Chat

## ✅ WebSocket Support verfügbar!

Da Sie die Bezahlvariante von PythonAnywhere haben, können Sie WebSockets und damit die vollständige Video Chat Funktionalität nutzen!

## PythonAnywhere Deployment mit WebSocket Support

### Schritt 1: Git Repository vorbereiten
```bash
# Sensitive Daten entfernen
git rm --cached Schuch/settings.py
echo "Schuch/settings.py" >> .gitignore

# Requirements.txt für Production
cp requirements.txt requirements_production.txt
# BEHALTEN Sie: channels, channels-redis, daphne (für WebSocket Support)
```

### Schritt 2: PythonAnywhere Konfiguration

#### A) Web Tab Einstellungen:
- **Python Version**: 3.10
- **Source Code**: `/home/yourusername/Arealo-Schuch`
- **Working Directory**: `/home/yourusername/Arealo-Schuch`
- **ASGI File**: `/var/www/yourusername_pythonanywhere_com_asgi.py` (WICHTIG: ASGI für WebSockets!)

#### B) ASGI File erstellen (für WebSocket Support):
```python
import os
import sys

# Add your project directory to sys.path
project_home = '/home/yourusername/Arealo-Schuch'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['DJANGO_SETTINGS_MODULE'] = 'Schuch.settings_production'

from Schuch.asgi import application
```

#### C) Production Settings erstellen:
```python
# Schuch/settings_production.py
from .settings import *

# PythonAnywhere spezifische Einstellungen
DEBUG = False
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']

# WebSocket Features BEHALTEN (da Sie bezahlte Version haben)
# ASGI_APPLICATION bleibt aktiviert
# CHANNEL_LAYERS bleibt aktiviert

# Redis für Channel Layers (falls verfügbar auf PythonAnywhere)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Static Files für Production
STATIC_ROOT = '/home/yourusername/Arealo-Schuch/staticfiles'

# Database für Production (SQLite auf PythonAnywhere)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/home/yourusername/Arealo-Schuch/db.sqlite3',
    }
}

# Neue Secret Key generieren
SECRET_KEY = 'your-new-production-secret-key'
```

### Schritt 3: WebSocket Konfiguration für PythonAnywhere

#### WebSocket URL Anpassung für Production:
```javascript
// chat/templates/chat/home_new.html - WebSocket Connection anpassen
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsHost = window.location.host;
const websocket = new WebSocket(`${wsProtocol}//${wsHost}/ws/chat/${roomId}/`);

// Für Video Calls
const callWebsocket = new WebSocket(`${wsProtocol}//${wsHost}/ws/call/${roomId}/`);
```

#### HTTPS Enforcement (wichtig für WebRTC):
```python
# settings_production.py hinzufügen
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Für WebRTC ist HTTPS zwingend erforderlich!
```

### Schritt 4: Deployment Checklist

```bash
# 1. Code hochladen
git clone https://github.com/your-repo/Arealo-Schuch.git
cd Arealo-Schuch

# 2. Virtual Environment
python3.10 -m venv venv
source venv/bin/activate

# 3. Dependencies installieren (MIT WebSocket packages für bezahlte Version)
pip install -r requirements_production.txt

# 4. Database Setup
python manage.py migrate --settings=Schuch.settings_production
python manage.py collectstatic --settings=Schuch.settings_production

# 5. Superuser erstellen
python manage.py createsuperuser --settings=Schuch.settings_production
```

### Schritt 5: Funktionen die funktionieren werden:

✅ **Video Calls** (mit WebSocket Support)
✅ **Audio Calls** (mit WebSocket Support)
✅ **Real-time Chat** (WebSocket)
✅ **Live Notifications**
✅ **Alle WebSocket basierten Features**
✅ **File Uploads**
✅ **User Management**
✅ **Login/Logout Tracking**

### Schritt 6: Wichtige Hinweise für Video Calls:

⚠️ **HTTPS ist zwingend erforderlich** für WebRTC Video/Audio Calls
⚠️ **Browser Permissions** müssen für Kamera/Mikrofon erteilt werden
⚠️ **Firewall Settings** können WebRTC P2P Verbindungen blockieren

### Schritt 7: Testing nach Deployment:

1. **WebSocket Connection testen:**
   ```javascript
   // Browser Console
   const ws = new WebSocket('wss://yourusername.pythonanywhere.com/ws/chat/1/');
   ws.onopen = () => console.log('WebSocket connected!');
   ```

2. **Video Call testen:**
   - Zwei Browser Tabs öffnen
   - In verschiedenen Accounts anmelden
   - Video Call starten

## Zusammenfassung

Mit der bezahlten PythonAnywhere Version haben Sie vollständigen WebSocket Support und können alle Video Chat Features nutzen! Die wichtigsten Punkte:

1. **ASGI statt WSGI** verwenden
2. **HTTPS aktivieren** (für WebRTC erforderlich)
3. **WebSocket URLs** für Production anpassen
4. **Channel Layers** konfigurieren
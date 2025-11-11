# 🐍 PythonAnywhere Deployment Guide

## Übersicht

Bei **PythonAnywhere** können wir nicht auf nginx zugreifen. Deshalb haben wir eine **Django-basierte Lösung** implementiert: Media-Dateien werden durch eine Django-View mit CORS-Headern serviert.

## 🎯 Ein-Kommando Deployment

```bash
# 1. SSH zu PythonAnywhere
ssh deinuser@ssh.pythonanywhere.com

# 2. Gehe zum Projekt
cd ~/Arealo-Schuch-Django

# 3. Führe Deployment-Script aus
./deploy-pythonanywhere.sh
```

**WICHTIG:** Nach dem Script musst du die Web-App manuell neu laden (siehe unten)!

## 📋 Was wurde implementiert?

### Neue Django-View: `serve_media_with_cors`

**Datei:** `shopify_uploads/views.py`

```python
@csrf_exempt
@cors_headers
def serve_media_with_cors(request, file_path):
    """
    Serviert Media-Dateien mit CORS-Headern.
    Workaround für PythonAnywhere.
    """
    # Lädt Datei aus MEDIA_ROOT
    # Fügt CORS-Header hinzu
    # Serviert mit korrektem Content-Type
```

### Neue URL-Route

**Datei:** `shopify_uploads/urls.py`

```python
re_path(r'^media/(?P<file_path>.+)$', views.serve_media_with_cors, name='serve_media'),
```

**Beispiel-URLs:**
- **Alt (funktioniert nicht):** `https://www.workloom.de/media/fotogravur/test.png`
- **Neu (mit CORS):** `https://www.workloom.de/shopify-uploads/media/fotogravur/test.png`

### URL-Anpassungen

Die Views `upload_image` und `get_image` geben jetzt URLs über den CORS-Proxy zurück:

```python
# Hilfsfunktion
def get_media_url_with_cors(request, file_field):
    file_path = file_field.name
    proxy_url = f'/shopify-uploads/media/{file_path}'
    return request.build_absolute_uri(proxy_url)
```

## 🚀 Deployment-Schritte

### Schritt 1: SSH-Verbindung

```bash
# Mit SSH verbinden
ssh deinuser@ssh.pythonanywhere.com

# Oder über PythonAnywhere Web-Interface:
# Dashboard → Consoles → Bash
```

### Schritt 2: Deployment ausführen

```bash
cd ~/Arealo-Schuch-Django
git pull origin master
./deploy-pythonanywhere.sh
```

Das Script macht:
1. ✅ Git pull
2. ✅ Virtual Environment aktivieren
3. ✅ Python Cache löschen
4. ✅ Dependencies installieren
5. ✅ Migrations ausführen
6. ✅ Static files sammeln

### Schritt 3: Web-App neu laden (WICHTIG!)

**PythonAnywhere lädt Code NICHT automatisch neu!**

1. Gehe zu: https://www.pythonanywhere.com/user/TarasYuzkiv/webapps/
2. Finde deine Web-App:
   - `tarasyuzkiv.pythonanywhere.com` oder
   - `workloom.de` (Custom Domain)
3. Klicke auf den **grünen "Reload" Button** oben rechts

**Screenshot-Position:**
```
Web
│
├─ tarasyuzkiv.pythonanywhere.com
│  └─ [Reload] ← HIER KLICKEN!
```

## 🧪 Testing

### 1. Desktop-Test
```bash
# 1. Öffne Browser
https://naturmacher.de/products/blumentopf-mit-fotogravur

# 2. Lade ein Bild hoch

# 3. Erwartete Debug-Logs:
✅ Original-Bild erfolgreich hochgeladen
URL: https://www.workloom.de/shopify-uploads/media/fotogravur/...
✅ Bild von workloom.de geladen: 1024x768
⚙️ Starte processUploadedImage...
✅ handleImageUpload ABGESCHLOSSEN
```

### 2. Mobile-Test (KRITISCH!)
- Öffne auf Handy: https://naturmacher.de/products/blumentopf-mit-fotogravur
- Lade ein Bild hoch
- Sollte jetzt funktionieren!

### 3. Admin-Prüfung
```bash
# Admin öffnen
https://www.workloom.de/admin/shopify_uploads/fotogravurimage/

# Neuestes Bild sollte sichtbar sein
# Beide Downloads sollten funktionieren
```

### 4. Direct URL Test
```bash
# Teste CORS-Proxy direkt
curl -I -H "Origin: https://naturmacher.de" \
     https://www.workloom.de/shopify-uploads/media/fotogravur/originals/2025/11/test.png

# Erwartete Header:
Access-Control-Allow-Origin: https://naturmacher.de
Content-Type: image/png
```

## 🔧 Manuelle Schritte (falls Script nicht funktioniert)

### Option 1: Über Bash Console (PythonAnywhere Dashboard)

```bash
# 1. Dashboard → Consoles → Start new console: Bash

# 2. Im Terminal:
cd ~/Arealo-Schuch-Django
git pull origin master
source venv/bin/activate  # Falls vorhanden
python manage.py migrate
python manage.py collectstatic --noinput

# 3. Gehe zu Web → Reload Button klicken
```

### Option 2: Über Files Tab

```bash
# 1. Dashboard → Files
# 2. Navigiere zu: /home/deinuser/Arealo-Schuch-Django
# 3. Browse zu den geänderten Dateien
# 4. Prüfe ob neuester Code vorhanden ist

# 5. Web → Reload Button klicken
```

## 🐛 Troubleshooting

### Problem: "Module not found" nach Deployment

**Lösung:**
```bash
cd ~/Arealo-Schuch-Django
source venv/bin/activate
pip install -r requirements.txt
```

Dann Web-App neu laden.

### Problem: Static files nicht geladen

**Lösung:**
```bash
python manage.py collectstatic --noinput --clear
```

Prüfe Web-App Config:
- **Static files:** `/static/` → `/home/deinuser/Arealo-Schuch-Django/staticfiles/`
- **Media files:** `/media/` → `/home/deinuser/Arealo-Schuch-Django/media/`

### Problem: "Access-Control-Allow-Origin" header fehlt

**Diagnose:**
```bash
# 1. Prüfe ob neue View deployed ist
cd ~/Arealo-Schuch-Django
git log -1 --oneline
# Sollte zeigen: "Add Django CORS proxy for media files"

# 2. Prüfe ob Web-App neu geladen wurde
# Web → Check "Last reload" timestamp

# 3. Teste View direkt
curl -I https://www.workloom.de/shopify-uploads/media/test.png
```

### Problem: 404 für /shopify-uploads/media/

**Lösung:**
```bash
# 1. Prüfe URLs config
cd ~/Arealo-Schuch-Django
grep -r "serve_media_with_cors" shopify_uploads/

# 2. Prüfe ob in urls.py vorhanden
cat shopify_uploads/urls.py

# 3. Web-App neu laden
```

### Problem: FileReader Error (Mobile)

Das sollte jetzt nicht mehr vorkommen! Falls doch:
1. Leere Browser-Cache
2. Prüfe Debug-Logs
3. Teste ob Backend deployed ist: `git log -1`

## 📊 Flow-Diagramm (PythonAnywhere)

```
Benutzer wählt Bild auf naturmacher.de
        ↓
FileReader.readAsDataURL() (sofort!)
        ↓
POST https://www.workloom.de/shopify-uploads/api/upload/
  Body: { original_image_data: "data:image...", unique_id: "..." }
        ↓
Django: Speichert Bild in MEDIA_ROOT
        ↓
Response: { original_image_url: "https://www.workloom.de/shopify-uploads/media/..." }
        ↓
Frontend: img.src = original_image_url
        ↓
Browser: GET https://www.workloom.de/shopify-uploads/media/...
        ↓
Django: serve_media_with_cors() View
  - Lädt Datei aus MEDIA_ROOT
  - Fügt CORS-Header hinzu
  - Serviert mit FileResponse
        ↓
Browser: Lädt Bild erfolgreich ✅
```

## 📁 Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `deploy-pythonanywhere.sh` | Automatisches Deployment-Script |
| `shopify_uploads/views.py` | `serve_media_with_cors()` View |
| `shopify_uploads/urls.py` | URL-Route für Media-Proxy |
| `PYTHONANYWHERE_DEPLOYMENT.md` | Diese Datei |

## 🔄 Unterschied zu nginx-Lösung

| Aspekt | nginx (Standard Server) | Django (PythonAnywhere) |
|--------|------------------------|-------------------------|
| CORS-Header | nginx.conf | Django View |
| Performance | ⚡ Schnell (direct file) | 🐢 Langsamer (Python) |
| Konfiguration | nginx -t && reload | Web-App Reload |
| Zugriff | SSH + root | Web-Interface |
| Media URL | `/media/...` | `/shopify-uploads/media/...` |

## ✅ Checklist nach Deployment

- [ ] Git pull erfolgreich
- [ ] Migrations ausgeführt
- [ ] Collectstatic ausgeführt
- [ ] **Web-App neu geladen** (WICHTIG!)
- [ ] Desktop-Test: Bild hochgeladen
- [ ] Mobile-Test: Bild hochgeladen
- [ ] Admin: Neue Bilder sichtbar
- [ ] CORS-Header: curl-Test erfolgreich

## 🎉 Fertig!

Nach erfolgreichem Deployment sollte der Bild-Upload auf **Desktop** und **Mobile** funktionieren!

Bei Problemen:
- PythonAnywhere Error Logs: Web → Log files → Error log
- Django Logs: `tail -f ~/Arealo-Schuch-Django/django.log`
- Server Logs: Web → Log files → Server log

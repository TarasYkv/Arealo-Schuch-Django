# 🚀 Fotogravur Server-Upload Feature - Deployment Guide

## Übersicht

Dieses Feature ermöglicht es, Bilder **sofort** nach der Auswahl zu workloom.de hochzuladen und von dort zu laden. Dies löst das **Mobile File-Problem**, bei dem FileReader auf mobilen Geräten fehlschlägt.

## Problem, das wir lösen

**Vorher:**
- Bild wird vom lokalen File-Objekt gelesen
- ❌ Auf Mobile: `NotReadableError` - File-Objekt wird ungültig
- ❌ Keine Vorschau auf Mobile

**Nachher:**
- ✅ Bild wird SOFORT zu workloom.de hochgeladen (FileReader läuft synchron)
- ✅ Bild wird von workloom.de URL geladen
- ✅ Funktioniert auf Desktop UND Mobile!

## 🎯 Komplettes Deployment in EINEM Befehl

```bash
ssh dein-server
cd /home/deinuser/Arealo-Schuch-Django
./deploy-complete.sh
```

**Das war's!** Das Script macht automatisch:
1. ✅ Git pull (neuester Code)
2. ✅ Python Cache löschen
3. ✅ Migrations (falls nötig)
4. ✅ Gunicorn neustart
5. ✅ nginx-Konfiguration finden
6. ✅ CORS-Block hinzufügen
7. ✅ nginx Konfiguration testen
8. ✅ nginx neu laden
9. ✅ CORS-Header testen

## 📋 Schritt-für-Schritt (falls du mehr Kontrolle willst)

### Option 1: Einzelne Scripts ausführen

#### Schritt 1: Django Backend
```bash
cd /home/deinuser/Arealo-Schuch-Django
./deploy-fotogravur.sh
```

#### Schritt 2: nginx CORS
```bash
./setup-nginx-cors.sh
```

### Option 2: Komplett manuell

#### 1. Django Backend
```bash
cd /home/deinuser/Arealo-Schuch-Django
git pull origin master
python manage.py migrate
sudo systemctl restart gunicorn
```

#### 2. nginx CORS

Siehe detaillierte Anleitung: [NGINX_CORS_SETUP.md](NGINX_CORS_SETUP.md)

Kurz:
```bash
sudo nano /etc/nginx/sites-available/workloom.de
# Füge CORS-Block hinzu (siehe nginx_media_cors.conf)
sudo nginx -t
sudo systemctl reload nginx
```

## 🧪 Testing

### 1. Desktop-Test
1. Gehe zu: https://naturmacher.de/products/blumentopf-mit-fotogravur
2. Lade ein Bild hoch
3. Erwartete Debug-Logs:
   ```
   ✅ Original-Bild erfolgreich hochgeladen
   URL: https://www.workloom.de/media/...
   ✅ Bild von workloom.de geladen: 1024x768
   ⚙️ Starte processUploadedImage...
   ✅ handleImageUpload ABGESCHLOSSEN
   ```

### 2. Mobile-Test (WICHTIG!)
1. Öffne auf deinem Handy: https://naturmacher.de/products/blumentopf-mit-fotogravur
2. Lade ein Bild hoch
3. Sollte jetzt OHNE Fehler funktionieren!
4. Kopiere Debug-Logs mit dem Copy-Button

### 3. Admin-Prüfung
1. Gehe zu: https://www.workloom.de/admin/shopify_uploads/fotogravurimage/
2. Neuestes Bild sollte sichtbar sein
3. Beide Downloads sollten funktionieren (S/W + Original)

### 4. CORS-Header-Test (CLI)
```bash
curl -I -H "Origin: https://naturmacher.de" \
     https://www.workloom.de/media/fotogravur/originals/2025/11/test.png
```

Erwartete Header:
```
Access-Control-Allow-Origin: https://naturmacher.de
Access-Control-Allow-Methods: GET, OPTIONS
```

## 📁 Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `deploy-complete.sh` | **Master-Script** - Führt alles aus |
| `deploy-fotogravur.sh` | Django Backend Deployment |
| `setup-nginx-cors.sh` | Automatisches nginx CORS Setup |
| `NGINX_CORS_SETUP.md` | Detaillierte nginx Anleitung |
| `nginx_media_cors.conf` | Beispiel nginx-Konfiguration |
| `DEPLOYMENT.md` | Diese Datei |

## 🔧 Was wurde geändert?

### Backend (`shopify_uploads/views.py`)
- **2-Phasen-Upload:**
  1. Initial: Nur `original_image_data` + `unique_id`
  2. Update: `image_data` (S/W-Bild) + `unique_id`
- **Absolute URLs:** `request.build_absolute_uri()` für Cross-Origin
- **Safe Templates:** Prüfen auf leere `image`/`original_image` Felder

### Frontend (`assets/fotogravur-preview.js`)
- **Neue Funktion:** `uploadOriginalImageImmediately(file)`
  - FileReader SOFORT ohne async Ops davor
  - Upload zu workloom.de
  - Gibt `unique_id` + `original_image_url` zurück
- **`handleImageUpload()` vereinfacht:**
  - Lädt Bild von workloom.de URL
  - Keine komplexe Blob-URL-Strategie mehr
- **`uploadImageToServer()` angepasst:**
  - Verwendet gespeicherte `currentUniqueId`
  - Update statt Insert

### nginx
- **CORS-Header für `/media/`:**
  - `Access-Control-Allow-Origin: https://naturmacher.de`
  - Preflight OPTIONS Handling
  - Cache-Header für Performance

## 🐛 Troubleshooting

### Problem: Bild lädt nicht (404)
**Lösung:**
```bash
# Prüfe MEDIA_ROOT Pfad
python manage.py shell
>>> from django.conf import settings
>>> print(settings.MEDIA_ROOT)

# Prüfe nginx alias
sudo nano /etc/nginx/sites-available/workloom.de
# Suche: alias /pfad/zu/media/;
```

### Problem: CORS-Header fehlen
**Lösung:**
```bash
# Prüfe ob nginx CORS-Block vorhanden
sudo grep -A 10 "location /media/" /etc/nginx/sites-available/workloom.de

# Falls nicht, führe aus:
./setup-nginx-cors.sh
```

### Problem: FileReader Error auf Mobile
**Lösung:** Das sollte jetzt nicht mehr vorkommen! Falls doch:
1. Prüfe ob Backend deployed ist: `git log -1 --oneline`
2. Prüfe ob Frontend deployed ist: `shopify theme list`
3. Leere Browser-Cache auf Mobile

### Problem: Django Middleware wird nicht ausgeführt
**Das ist normal!** Media-Dateien werden von nginx serviert, nicht von Django. Die `MediaCORSMiddleware` wird nie aufgerufen. CORS muss in nginx konfiguriert werden.

## 📊 Flow-Diagramm

```
Benutzer wählt Bild
        ↓
FileReader.readAsDataURL() (SOFORT, synchron!)
        ↓
Upload zu workloom.de (Original-Bild)
        ↓
Speichere unique_id
        ↓
Lade Bild von workloom.de URL
        ↓
Verarbeite Bild (S/W, Dithering, etc.)
        ↓
Upload S/W-Bild (Update mit gleicher unique_id)
        ↓
Füge zu Warenkorb hinzu
```

## 🎉 Fertig!

Nach erfolgreichem Deployment sollte der Bild-Upload sowohl auf **Desktop** als auch auf **Mobile** funktionieren!

Bei Fragen oder Problemen:
- Prüfe nginx Logs: `sudo tail -f /var/log/nginx/error.log`
- Prüfe Django Logs: `sudo journalctl -u gunicorn -f`
- Prüfe Debug-Logs im Frontend (Copy-Button)

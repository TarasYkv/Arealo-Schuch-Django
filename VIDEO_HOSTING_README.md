# Video Hosting App - Schuch Platform

Eine vollständige Video-Hosting-Lösung für die Schuch-Platform, die es ermöglicht, Videos hochzuladen, zu konvertieren und über einzigartige Links zu teilen.

## 🚀 Features

- **Video-Upload**: Unterstützt MP4, AVI, MOV, WMV, FLV, MKV, WebM
- **Automatische Konvertierung**: Videos werden in web-optimiertes H.264/MP4-Format konvertiert
- **Speicherplatz-Management**: 50MB kostenlos pro User, erweiterbares Abo-System
- **Unique Sharing-Links**: Sichere UUID-basierte Links für jedes Video
- **Embed-Support**: iFrame-Integration für Blogs und Websites
- **Video-Streaming**: Range-Request-Unterstützung für Seek-Funktionalität
- **Thumbnail-Generierung**: Automatische Vorschaubilder
- **Responsive Design**: Bootstrap-basierte UI

## 📁 Struktur

```
videos/
├── models.py          # Video, UserStorage, Subscription Models
├── views.py           # Upload, Streaming, Management Views
├── tasks.py           # Celery-Tasks für Video-Konvertierung
├── forms.py           # Upload-Formulare
├── urls.py            # URL-Konfiguration
├── admin.py           # Django Admin-Interface
└── templates/videos/  # HTML-Templates
    ├── video_list.html
    ├── video_upload.html
    ├── video_detail.html
    ├── video_view.html
    ├── video_embed.html
    └── video_confirm_delete.html
```

## 🛠 Installation & Setup

### 1. System-Abhängigkeiten installieren

```bash
# Script ausführen (empfohlen)
./install_dependencies.sh

# Oder manuell:
sudo apt install ffmpeg redis-server  # Ubuntu/Debian
brew install ffmpeg redis             # macOS
```

### 2. Python-Abhängigkeiten

Bereits in `requirements.txt` enthalten:
- celery==5.5.3
- redis==6.2.0
- pillow (für Thumbnail-Generierung)

### 3. Redis starten

```bash
sudo systemctl start redis-server  # Linux
brew services start redis          # macOS
```

### 4. Celery Worker starten

```bash
# Video-Processing Worker
celery -A Schuch worker --loglevel=info --queues=video_processing

# In separatem Terminal für alle Queues
celery -A Schuch worker --loglevel=info
```

## 📊 Models

### Video
- Benutzer-Zuordnung
- Original- und konvertierte Dateien
- Thumbnail-Unterstützung
- Status-Tracking (uploading, processing, ready, failed)
- UUID für sichere Links
- Metadaten (Größe, Dauer)

### UserStorage
- Speicherplatz-Tracking pro User
- 50MB Standard-Limit
- Premium-Erweiterungen

### Subscription
- Abo-Pläne für erweiterten Speicherplatz
- Basic (500MB), Pro (5GB), Business (50GB)

## 🔗 URLs

- `/videos/` - Video-Liste (authentifiziert)
- `/videos/upload/` - Video-Upload
- `/videos/detail/<id>/` - Video-Details (Owner)
- `/videos/v/<uuid>/` - Öffentliche Video-Ansicht
- `/videos/embed/<uuid>/` - Embeddable Player
- `/videos/stream/<uuid>/` - Video-Stream (mit Range-Support)

## 🎯 Verwendung für Shopify-Blogs

### 1. Video hochladen
```
1. Gehe zu /videos/upload/
2. Titel und optionale Beschreibung eingeben
3. Video-Datei auswählen
4. Upload starten
```

### 2. Link kopieren
```
1. Nach Upload: Video wird automatisch konvertiert
2. In Video-Liste: "Copy Link" für direkten Link
3. Für iFrame: Embed-Code kopieren
```

### 3. In Shopify-Blog verwenden
```html
<!-- Direkter Link -->
<a href="https://workloom.de/videos/v/uuid-hier/">Video ansehen</a>

<!-- Embedded Player -->
<iframe src="https://workloom.de/videos/embed/uuid-hier/" 
        width="640" height="360" frameborder="0" allowfullscreen>
</iframe>
```

## ⚙️ Konfiguration

### Celery Settings (in settings.py)
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_TASK_ROUTES = {
    'videos.tasks.convert_video': {'queue': 'video_processing'},
}
```

### Video-Konvertierung anpassen
In `videos/tasks.py` können ffmpeg-Parameter angepasst werden:
```python
cmd = [
    'ffmpeg',
    '-i', input_path,
    '-c:v', 'libx264',     # Video-Codec
    '-preset', 'medium',    # Geschwindigkeit/Qualität
    '-crf', '23',          # Qualität (niedriger = besser)
    # ...weitere Parameter
]
```

## 🔧 Erweiterte Features

### Speicherplatz-Limits anpassen
```python
# In videos/models.py
max_storage = models.BigIntegerField(default=52428800)  # 50MB in Bytes
```

### Unterstützte Video-Formate erweitern
```python
# In videos/models.py
validators=[FileExtensionValidator(
    allowed_extensions=['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'zusätzlich']
)]
```

## 🚨 Troubleshooting

### Video-Konvertierung schlägt fehl
1. Prüfe ffmpeg-Installation: `ffmpeg -version`
2. Prüfe Celery-Worker-Logs
3. Dateiberechtigungen prüfen

### Speicherplatz-Probleme
1. Bereinige verwaiste Dateien
2. Führe `cleanup_user_storage` Task aus
3. Prüfe MEDIA_ROOT-Konfiguration

### Redis-Verbindung
1. Prüfe Redis-Status: `redis-cli ping`
2. Starte Redis neu: `sudo systemctl restart redis-server`

## 📈 Monitoring

### Celery-Tasks überwachen
```bash
# Task-Status anzeigen
celery -A Schuch inspect active

# Worker-Status
celery -A Schuch inspect stats
```

### Speicherplatz-Übersicht
Im Django-Admin unter "Videos > User Storage" verfügbar.

---

**Entwickelt für die Schuch-Platform** - Video-Hosting-Lösung für Shopify-Blog-Integration
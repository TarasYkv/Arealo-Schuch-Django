# Nginx CORS Setup für Fotogravur (naturmacher.de ⟷ workloom.de)

## Problem
Media-Dateien werden von **nginx** serviert, nicht von Django. Deshalb funktioniert die Django-Middleware nicht für `/media/` URLs. CORS-Header müssen in der **nginx-Konfiguration** gesetzt werden.

## Lösung

### 1. Finde deine nginx-Konfiguration

```bash
# Übliche Pfade:
sudo nano /etc/nginx/sites-available/workloom.de
# oder
sudo nano /etc/nginx/conf.d/workloom.de.conf
# oder
sudo nano /etc/nginx/nginx.conf
```

### 2. Füge den CORS-Block für /media/ hinzu

Füge diesen Block **innerhalb deines `server { }` Blocks** hinzu:

```nginx
location /media/ {
    alias /home/deinuser/Arealo-Schuch-Django/media/;  # ⚠️ PASSE DEN PFAD AN!

    # CORS-Header für naturmacher.de
    add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
    add_header 'Access-Control-Max-Age' '86400' always;

    # Handle OPTIONS preflight requests
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
        add_header 'Access-Control-Max-Age' '86400' always;
        add_header 'Content-Type' 'text/plain charset=UTF-8';
        add_header 'Content-Length' 0;
        return 204;
    }

    # Cache-Header für Performance
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

**WICHTIG:** Passe `alias /home/deinuser/Arealo-Schuch-Django/media/;` an deinen tatsächlichen Pfad an!

### 3. Media-Pfad herausfinden

Falls du den Pfad nicht kennst:

```bash
# In deinem Django-Projekt:
python manage.py shell
>>> from django.conf import settings
>>> print(settings.MEDIA_ROOT)
/home/deinuser/Arealo-Schuch-Django/media
```

### 4. Nginx-Konfiguration testen

```bash
sudo nginx -t
```

Erwartete Ausgabe:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 5. Nginx neu laden

```bash
sudo systemctl reload nginx
```

### 6. CORS-Header testen

```bash
curl -I -H "Origin: https://naturmacher.de" \
     https://www.workloom.de/media/fotogravur/originals/2025/11/test.png
```

Erwartete Header:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://naturmacher.de
Access-Control-Allow-Methods: GET, OPTIONS
...
```

### 7. Funktionstest

1. Gehe zu: https://naturmacher.de/products/blumentopf-mit-fotogravur
2. Lade ein Bild hoch (besonders auf Mobile!)
3. Prüfe Debug-Logs:
   - `✅ Original-Bild erfolgreich hochgeladen`
   - `✅ Bild von workloom.de geladen: 1024x768`

## Vollständige Beispiel-Konfiguration

```nginx
server {
    listen 443 ssl http2;
    server_name workloom.de www.workloom.de;

    # SSL-Zertifikate
    ssl_certificate /etc/letsencrypt/live/workloom.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/workloom.de/privkey.pem;

    # Static files
    location /static/ {
        alias /home/deinuser/Arealo-Schuch-Django/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files mit CORS
    location /media/ {
        alias /home/deinuser/Arealo-Schuch-Django/media/;

        add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
        add_header 'Access-Control-Max-Age' '86400' always;

        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
            add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
            add_header 'Access-Control-Max-Age' '86400' always;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Django application
    location / {
        proxy_pass http://unix:/run/gunicorn.sock;  # Oder http://127.0.0.1:8000
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Problem: "Access-Control-Allow-Origin" header fehlt

**Lösung:** Prüfe, ob der `location /media/` Block korrekt eingefügt wurde.

### Problem: 404 Not Found für /media/

**Lösung:** Prüfe den `alias` Pfad:
```bash
ls -la /home/deinuser/Arealo-Schuch-Django/media/
```

### Problem: Permission Denied

**Lösung:** Setze korrekte Berechtigungen:
```bash
sudo chown -R www-data:www-data /home/deinuser/Arealo-Schuch-Django/media/
sudo chmod -R 755 /home/deinuser/Arealo-Schuch-Django/media/
```

### Problem: nginx -t zeigt Fehler

**Lösung:** Prüfe Syntax:
- Fehlende Semikolons?
- Geschweifte Klammern korrekt geschlossen?
- Pfad existiert?

## Weitere Hilfe

- Vollständige nginx-Beispielkonfiguration: `nginx_media_cors.conf`
- Deployment-Script: `./deploy-fotogravur.sh`
- nginx Logs: `sudo tail -f /var/log/nginx/error.log`

# Nginx WebSocket-Konfiguration für workloom.de

## Schritt-für-Schritt Anleitung

### 1. Nginx-Konfigurationsdatei finden
```bash
# Auf dem Server ausführen:
sudo find /etc/nginx -name "*.conf" -type f | grep -E "(sites-|default|workloom)"

# Oder typische Pfade prüfen:
ls -la /etc/nginx/sites-available/
ls -la /etc/nginx/sites-enabled/
ls -la /etc/nginx/conf.d/
```

### 2. Backup der aktuellen Konfiguration erstellen
```bash
# Ersetze PFAD_ZU_DEINER_CONFIG mit dem tatsächlichen Pfad
sudo cp /etc/nginx/sites-available/workloom.de /etc/nginx/sites-available/workloom.de.backup.$(date +%Y%m%d)
```

### 3. Konfigurationsdatei bearbeiten
```bash
# Öffne die Konfigurationsdatei
sudo nano /etc/nginx/sites-available/workloom.de

# Oder mit vim:
sudo vim /etc/nginx/sites-available/workloom.de
```

### 4. WebSocket-Konfiguration hinzufügen

**WICHTIG**: Füge diese Zeilen INNERHALB deines bestehenden `server`-Blocks hinzu:

```nginx
# WebSocket-Proxy für Anruf-Funktion
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;
}
```

### 5. Beispiel einer vollständigen Konfiguration

```nginx
server {
    listen 80;
    server_name workloom.de www.workloom.de;
    
    # Normale Django-Requests
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket-Requests (NEU)
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
    
    # Statische Dateien (falls vorhanden)
    location /static/ {
        alias /pfad/zu/static/dateien/;
    }
    
    location /media/ {
        alias /pfad/zu/media/dateien/;
    }
}
```

### 6. Konfiguration testen
```bash
# Syntax prüfen
sudo nginx -t

# Sollte ausgeben: "syntax is ok" und "test is successful"
```

### 7. Nginx neu laden
```bash
# Konfiguration neu laden (ohne Downtime)
sudo systemctl reload nginx

# Oder komplett neustarten
sudo systemctl restart nginx
```

### 8. Status prüfen
```bash
# Nginx-Status prüfen
sudo systemctl status nginx

# Ports prüfen
sudo netstat -tlnp | grep nginx
# oder
sudo ss -tlnp | grep nginx
```

### 9. ASGI-Server starten
```bash
# Im Projektverzeichnis
cd /pfad/zu/deinem/projekt
source venv/bin/activate
nohup daphne -b 127.0.0.1 -p 8001 Schuch.asgi:application > websocket.log 2>&1 &
```

## Troubleshooting

### Fehler: "nginx: [emerg] bind() to 0.0.0.0:80 failed"
```bash
# Prüfe was Port 80 verwendet
sudo netstat -tlnp | grep :80
sudo systemctl stop apache2  # Falls Apache läuft
```

### Fehler: "proxy_pass" failed
```bash
# Prüfe ob ASGI-Server läuft
netstat -tlnp | grep 8001
```

### WebSocket-Verbindung schlägt fehl
```bash
# Prüfe Logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Test der WebSocket-Verbindung
```bash
# Mit curl testen
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" http://workloom.de/ws/call/1/
```

## Automatisierung

### Systemd-Service für ASGI-Server erstellen
```bash
sudo nano /etc/systemd/system/django-websocket.service
```

```ini
[Unit]
Description=Django WebSocket Server
After=network.target

[Service]
Type=simple
User=dein_user
WorkingDirectory=/pfad/zu/deinem/projekt
ExecStart=/pfad/zu/deinem/projekt/venv/bin/daphne -b 127.0.0.1 -p 8001 Schuch.asgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable django-websocket
sudo systemctl start django-websocket
```
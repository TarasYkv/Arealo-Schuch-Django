# WebSocket-Konfiguration für Anruf-Funktion

## Problem
Die Anruf-Funktion benötigt WebSocket-Verbindungen, die aktuell nicht verfügbar sind.

## Lösung

### 1. Redis-Server installieren und starten
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis

# Redis starten
sudo systemctl start redis
sudo systemctl enable redis
```

### 2. ASGI-Server starten
```bash
# Im Projektverzeichnis
./start_websocket.sh

# Oder manuell:
source venv/bin/activate
daphne -b 127.0.0.1 -p 8001 Schuch.asgi:application
```

### 3. Nginx-Konfiguration aktualisieren
Füge diese Konfiguration zu deiner Nginx-Konfiguration hinzu:

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
}
```

### 4. Nginx neu laden
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Systemd-Service erstellen (optional)
```bash
sudo nano /etc/systemd/system/django-websocket.service
```

```ini
[Unit]
Description=Django WebSocket Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/pfad/zum/projekt
ExecStart=/pfad/zum/projekt/venv/bin/daphne -b 127.0.0.1 -p 8001 Schuch.asgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable django-websocket
sudo systemctl start django-websocket
```

## Test
Nach der Konfiguration sollte die WebSocket-Verbindung funktionieren:
- Öffne den Chat
- Die Fehlermeldung sollte verschwinden
- Anruf-Buttons sollten sichtbar sein

## Troubleshooting

### Redis-Verbindungsfehler
```bash
# Redis-Status prüfen
redis-cli ping
# Sollte "PONG" zurückgeben
```

### WebSocket-Verbindungsfehler
```bash
# Prüfe ob ASGI-Server läuft
netstat -tlnp | grep 8001

# Prüfe Nginx-Konfiguration
sudo nginx -t
```

### Logs prüfen
```bash
# Django-Logs
tail -f /var/log/django/error.log

# Nginx-Logs
tail -f /var/log/nginx/error.log
```
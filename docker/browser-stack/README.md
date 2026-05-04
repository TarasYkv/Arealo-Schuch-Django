# Backloom Browser-Stack

Docker-Container fuer headed Chromium mit noVNC-Live-View. Wird vom Backloom-
Bot ueber HTTP-Control-API gesteuert.

## Komponenten

- **Xvfb** – virtueller Bildschirm (Display `:99`, Default 1280x800)
- **fluxbox** – minimal Window-Manager (damit Chromium ein Eltern-Fenster hat)
- **x11vnc** – exposed Display als VNC (Port 5900, intern)
- **websockify+noVNC** – VNC -> WebSocket fuer Browser-Live-View (Port 6080)
- **Chromium** – wird on demand von der Control-API gestartet
- **Control-API** (FastAPI) – Endpoints `/sessions/start`, `/stop`, `/healthz`,
  `/screenshot` (Port 8888)

## Lifecycle

```
Workloom-Celery-Worker (Hetzner-Host)
     │  POST :8888/sessions/start
     ▼
Control-API → spawnt chromium auf Display :99
     │  liefert CDP-WebSocket-URL
     ▼
browser-use (im Worker) attached an Chromium per CDP
     │  Bot fuellt Forms, navigiert, ...
     │  parallel: User schaut zu via /backloom/browser/  (noVNC iframe)
     ▼
POST :8888/sessions/stop  → Chromium gekillt, Container bleibt up
```

## Build und Start

```bash
ssh root@178.104.110.45
cd /var/www/workloom/docker/browser-stack
docker compose build       # ~5-8 min beim ersten Mal
docker compose up -d
docker logs -f backloom-browser
```

## Healthcheck

```bash
curl http://localhost:8888/healthz
# → {"ok":true,"session_active":false,"uptime_s":12,...}
```

## Manueller Smoke-Test

```bash
# Session starten
curl -X POST http://localhost:8888/sessions/start \
     -H 'Content-Type: application/json' \
     -d '{"start_url":"https://naturmacher.de"}'

# Screenshot ziehen
curl -X POST http://localhost:8888/sessions/screenshot --output /tmp/shot.png

# noVNC im Browser:
# https://workloom.de/backloom/browser/  (nach nginx-Proxy-Setup)

# Aufraeumen
curl -X POST http://localhost:8888/sessions/stop
```

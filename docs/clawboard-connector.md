# Clawboard Connector - Architektur & Setup

## Übersicht

Der Clawboard Connector ermöglicht die Verbindung zwischen einem lokalen OpenClaw/Clawdbot Gateway und der Clawboard Web-App auf workloom.de.

**Prinzip:** Der lokale Agent verbindet sich *zu* Workloom (ausgehende Verbindung), ähnlich wie bei Telegram oder Discord. Dadurch ist kein Port-Forwarding oder Tunnel nötig.

```
┌─────────────────────┐              ┌─────────────────────┐
│  Lokaler PC         │              │  workloom.de        │
│  (Heimnetzwerk)     │              │  (Internet)         │
│                     │   WebSocket  │                     │
│  ┌───────────────┐  │   outbound   │  ┌───────────────┐  │
│  │ OpenClaw      │──┼──────────────┼─▶│ Clawboard     │  │
│  │ Gateway       │  │   wss://     │  │ WebSocket Hub │  │
│  └───────────────┘  │              │  └───────────────┘  │
│         │           │              │         │           │
│  ┌──────▼────────┐  │              │  ┌──────▼────────┐  │
│  │ Connector     │  │              │  │ Web Dashboard │  │
│  │ Service       │  │              │  │ (Browser)     │  │
│  └───────────────┘  │              │  └───────────────┘  │
└─────────────────────┘              └─────────────────────┘
```

## Komponenten

### 1. Clawboard WebSocket Hub (Server-Seite)
- **Ort:** workloom.de (Django Channels)
- **Endpoint:** `wss://www.workloom.de/ws/clawboard/gateway/`
- **Funktion:** Akzeptiert Verbindungen von Gateways, routet Nachrichten

### 2. Connector Service (Client-Seite)
- **Ort:** Lokaler PC mit OpenClaw
- **Funktion:** Verbindet sich zu Workloom, leitet Anfragen an lokalen Gateway weiter
- **Läuft als:** systemd user service

### 3. Clawboard Dashboard (Browser)
- **Ort:** Browser des Nutzers
- **Funktion:** Zeigt Status, Memory-Dateien, Konversationen an

## Kommunikationsprotokoll

### Authentifizierung
```json
// Client → Server (bei Verbindung)
{
  "type": "auth",
  "token": "user-generated-connection-token",
  "gateway_info": {
    "name": "optimus",
    "version": "2026.2.19",
    "hostname": "optimus"
  }
}

// Server → Client (Antwort)
{
  "type": "auth_result",
  "success": true,
  "connection_id": "uuid-here"
}
```

### Heartbeat (alle 30 Sekunden)
```json
// Client → Server
{
  "type": "heartbeat",
  "timestamp": 1234567890,
  "system": {
    "cpu_percent": 45.2,
    "ram_used_mb": 2048,
    "ram_total_mb": 4096,
    "disk_used_gb": 50.5,
    "disk_total_gb": 256
  }
}

// Server → Client
{
  "type": "heartbeat_ack"
}
```

### Befehle (Server → Client)
```json
// Memory-Datei lesen
{
  "type": "command",
  "id": "cmd-uuid",
  "action": "read_file",
  "params": {
    "path": "MEMORY.md"
  }
}

// Antwort
{
  "type": "command_result",
  "id": "cmd-uuid",
  "success": true,
  "data": {
    "content": "# MEMORY.md...",
    "modified": "2026-02-19T21:00:00Z"
  }
}
```

### Verfügbare Aktionen
| Action | Beschreibung | Parameter |
|--------|--------------|-----------|
| `read_file` | Datei lesen | `path` |
| `write_file` | Datei schreiben | `path`, `content` |
| `list_files` | Dateien auflisten | `directory` |
| `get_status` | System-Status | - |
| `get_sessions` | Sessions auflisten | - |
| `get_cron_jobs` | Cron-Jobs auflisten | - |
| `send_message` | Nachricht senden | `session`, `message` |

## Setup-Anleitung

### Schritt 1: Workloom Account
1. Registriere dich auf https://www.workloom.de
2. Gehe zu Clawboard → Verbindungen → Neue Verbindung
3. Notiere dir den generierten **Connection Token**

### Schritt 2: Connector installieren (auf dem PC mit OpenClaw)

```bash
# Connector-Script herunterladen
curl -o ~/.clawdbot/clawboard-connector.py \
  https://raw.githubusercontent.com/TarasYkv/Arealo-Schuch-Django/master/clawboard/connector/connector.py

# Konfiguration erstellen
cat > ~/.clawdbot/clawboard-connector.json << EOF
{
  "workloom_url": "wss://www.workloom.de/ws/clawboard/gateway/",
  "connection_token": "DEIN-TOKEN-HIER",
  "gateway_url": "ws://localhost:18789",
  "gateway_token": "dein-gateway-token"
}
EOF

# Service einrichten
cat > ~/.config/systemd/user/clawboard-connector.service << EOF
[Unit]
Description=Clawboard Connector
After=network-online.target clawdbot-gateway.service
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 %h/.clawdbot/clawboard-connector.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

# Aktivieren
systemctl --user daemon-reload
systemctl --user enable --now clawboard-connector.service
```

### Schritt 3: Verbindung prüfen
- Gehe zu https://www.workloom.de/clawboard/
- Deine Verbindung sollte als "Online" angezeigt werden

## Für den Agenten (OpenClaw/Clawdbot)

### Memory-Eintrag
Der Agent sollte wissen:
- Clawboard läuft auf workloom.de
- Connector-Service verbindet automatisch
- Status prüfen: `systemctl --user status clawboard-connector`
- Logs: `journalctl --user -u clawboard-connector -f`

### Bei Problemen
1. Connector-Status prüfen
2. Gateway läuft? `systemctl --user status clawdbot-gateway`
3. Token korrekt in `~/.clawdbot/clawboard-connector.json`?
4. Workloom erreichbar? `curl https://www.workloom.de/health/`

## Sicherheit

- **Token:** Wird bei Workloom-Registrierung generiert, nur einmal angezeigt
- **Transport:** Immer WSS (verschlüsselt)
- **Authentifizierung:** Token-basiert, pro Verbindung
- **Berechtigungen:** Nur der Token-Besitzer kann die Verbindung sehen/nutzen

# Clawboard - Clawdbot Dashboard für WorkLoom

**Status:** 🟡 In Planung
**Version:** 0.1.0
**Erstellt:** 2025-02-09

---

## 📋 Projektübersicht

**Clawboard** ist ein Web-Dashboard zur Verwaltung und Interaktion mit Clawdbot-Instanzen. Jeder User kann seinen eigenen Clawdbot verbinden und erhält Einblick in Projekte, Aufgaben, Erinnerungen und konfigurierte Integrationen.

---

## 🎯 Kern-Features

### 1. **Clawdbot-Verbindung**
- Gateway-URL + Token Konfiguration
- Verbindungsstatus (online/offline)
- Mehrere Clawdbot-Instanzen pro User möglich

### 2. **Projekte**
- Projekte erstellen/bearbeiten/archivieren
- Status: Aktiv / Geplant / Abgeschlossen
- Timeline: Was wurde wann bearbeitet
- Memory-Einträge pro Projekt
- Tags und Kategorien

### 3. **Aufgaben & Erinnerungen**
- Cron-Jobs anzeigen/erstellen/bearbeiten (via Clawdbot API)
- Geplante Tasks
- Reminder-Übersicht
- Wiederkehrende Aufgaben

### 4. **Integrationen & Credentials**
- Status-Dashboard: ✅ Email | ✅ GitHub | ⚠️ Google Drive | ❌ Twitter
- Credentials verwalten (verschlüsselt in DB)
- Neue Integrationen hinzufügen ("Bausteine")
- Kategorien: API Keys, OAuth, CLI Tools, SSH, etc.

### 5. **Memory Browser**
- MEMORY.md Inhalt anzeigen
- Daily files (memory/YYYY-MM-DD.md) durchsuchen
- Timeline-Ansicht
- Suche in Memory-Einträgen

### 6. **Chat / Terminal** (Optional Phase 2)
- Direkt mit Clawdbot chatten
- Session-History einsehen
- WebSocket-Verbindung

---

## 🏗️ Datenbank-Modelle

### 1. ClawdbotConnection
```python
class ClawdbotConnection(models.Model):
    """Verbindung zu einer Clawdbot-Instanz"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # z.B. "Mein Laptop", "Server"
    gateway_url = models.URLField()
    gateway_token = models.CharField(max_length=500)  # verschlüsselt
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True)
    status = models.CharField(max_length=20)  # online, offline, error
    created_at = models.DateTimeField(auto_now_add=True)
```

### 2. Project
```python
class Project(models.Model):
    """Projekt das von Clawdbot bearbeitet wird"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)  # active, planned, completed, archived
    priority = models.CharField(max_length=20)  # low, medium, high
    color = models.CharField(max_length=7)  # Hex color
    icon = models.CharField(max_length=50, blank=True)  # Emoji oder Icon-Name
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 3. ProjectMemory
```python
class ProjectMemory(models.Model):
    """Memory-Eintrag zu einem Projekt"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    content = models.TextField()
    source = models.CharField(max_length=100)  # Datei-Quelle (z.B. memory/2025-02-09.md)
    entry_type = models.CharField(max_length=50)  # note, decision, task, idea
    created_at = models.DateTimeField(auto_now_add=True)
```

### 4. ScheduledTask
```python
class ScheduledTask(models.Model):
    """Geplante Aufgabe / Cron-Job"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, null=True, on_delete=models.SET_NULL)
    cron_job_id = models.CharField(max_length=100)  # ID vom Clawdbot
    name = models.CharField(max_length=200)
    schedule = models.CharField(max_length=100)  # Cron-Expression
    text = models.TextField()  # Was soll ausgeführt werden
    is_enabled = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True)
    next_run = models.DateTimeField(null=True)
```

### 5. Integration (Bausteine)
```python
class Integration(models.Model):
    """Konfigurierte Integration/Zugang"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE)
    
    CATEGORY_CHOICES = [
        ('api', 'API Key'),
        ('oauth', 'OAuth'),
        ('cli', 'CLI Tool'),
        ('ssh', 'SSH'),
        ('email', 'Email'),
        ('database', 'Database'),
        ('storage', 'Cloud Storage'),
        ('messaging', 'Messaging'),
        ('other', 'Sonstiges'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    name = models.CharField(max_length=100)  # z.B. "GitHub", "Zoho Mail"
    icon = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20)  # active, inactive, error, pending
    config = models.JSONField(default=dict)  # Verschlüsselte Konfiguration
    notes = models.TextField(blank=True)
    last_verified = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 6. IntegrationTemplate (Baustein-Vorlagen)
```python
class IntegrationTemplate(models.Model):
    """Vorlage für häufige Integrationen"""
    name = models.CharField(max_length=100)  # z.B. "GitHub"
    category = models.CharField(max_length=20)
    icon = models.CharField(max_length=50)
    description = models.TextField()
    config_schema = models.JSONField()  # Welche Felder benötigt werden
    setup_instructions = models.TextField()
    is_active = models.BooleanField(default=True)
```

---

## 🔌 API-Kommunikation mit Clawdbot

### Clawdbot Gateway API
Die Kommunikation läuft über die Clawdbot Gateway API:

```python
class ClawdbotAPI:
    def __init__(self, gateway_url: str, token: str):
        self.base_url = gateway_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def get_status(self) -> dict:
        """Gateway-Status abrufen"""
        pass
    
    def list_cron_jobs(self) -> list:
        """Alle Cron-Jobs abrufen"""
        pass
    
    def create_cron_job(self, schedule: str, text: str) -> dict:
        """Neuen Cron-Job erstellen"""
        pass
    
    def send_message(self, message: str) -> dict:
        """Nachricht an Clawdbot senden"""
        pass
    
    def get_config(self) -> dict:
        """Konfiguration abrufen (welche Integrationen aktiv)"""
        pass
```

---

## 📱 UI/UX Design

### Dashboard-Übersicht
```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Clawboard                          [Clawd] ● Online     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 📁 Projekte  │  │ ⏰ Aufgaben  │  │ 🔌 Integr.  │      │
│  │     3        │  │     5        │  │    12       │      │
│  │   Aktiv      │  │   Geplant    │  │   Aktiv     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  📊 Aktivität                                               │
│  ├── Heute: naturmacher SEO-Analyse                        │
│  ├── Gestern: Email-Setup abgeschlossen                    │
│  └── 07.02: Clawdbot installiert                           │
│                                                             │
│  🔧 Integrationen                                          │
│  ✅ GitHub (gh CLI)     ✅ Telegram      ⚠️ Google Drive   │
│  ✅ Zoho Mail           ✅ OpenAI API    ❌ Twitter        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 App-Struktur

```
clawboard/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── forms.py
├── api.py              # Clawdbot API Client
├── services.py         # Business Logic
├── signals.py
├── migrations/
├── templates/
│   └── clawboard/
│       ├── base.html
│       ├── dashboard.html
│       ├── projects/
│       │   ├── list.html
│       │   ├── detail.html
│       │   └── form.html
│       ├── tasks/
│       │   ├── list.html
│       │   └── form.html
│       ├── integrations/
│       │   ├── list.html
│       │   ├── detail.html
│       │   └── add.html
│       ├── memory/
│       │   └── browser.html
│       └── settings/
│           └── connection.html
└── static/
    └── clawboard/
        ├── css/
        └── js/
```

---

## 🚀 Implementierungs-Phasen

### Phase 1: Grundgerüst (MVP)
- [ ] Django App erstellen
- [ ] Models definieren
- [ ] Clawdbot-Verbindung Setup
- [ ] Dashboard mit Status-Anzeige
- [ ] Projekte CRUD
- [ ] Integrationen-Übersicht

### Phase 2: Erweiterung
- [ ] Cron-Jobs verwalten (via API)
- [ ] Memory Browser
- [ ] Aktivitäts-Timeline
- [ ] Baustein-Templates

### Phase 3: Chat & Echtzeit
- [ ] Chat-Interface
- [ ] WebSocket-Verbindung
- [ ] Echtzeit-Updates
- [ ] Session-History

---

## 🔒 Sicherheit

- Gateway-Tokens werden verschlüsselt in DB gespeichert
- Credentials nie im Klartext
- Rate-Limiting für API-Calls
- User kann nur eigene Connections sehen/bearbeiten

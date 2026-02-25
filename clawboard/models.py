from django.db import models
from django.conf import settings
from encrypted_model_fields.fields import EncryptedCharField


class ClawdbotConnection(models.Model):
    """Verbindung zu einer Clawdbot-Instanz"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clawdbot_connections')
    name = models.CharField(max_length=100, verbose_name="Name", help_text="z.B. 'Mein Laptop', 'Server'")
    gateway_url = models.URLField(verbose_name="Gateway URL", help_text="WebSocket URL des Clawdbot Gateway")
    gateway_token = EncryptedCharField(max_length=500, verbose_name="Gateway Token")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Zuletzt gesehen")
    
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Fehler'),
        ('unknown', 'Unbekannt'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown', verbose_name="Status")
    
    # Gateway-Info (vom Connector gesendet)
    hostname = models.CharField(max_length=200, blank=True, verbose_name="Hostname")
    gateway_version = models.CharField(max_length=50, blank=True, verbose_name="Gateway Version")
    
    # Pending Command (wird beim naechsten Push an Connector gesendet)
    pending_command = models.CharField(max_length=50, blank=True, verbose_name="Ausstehender Befehl")

    # OpenClaw Gateway API Token (fuer /v1/chat/completions etc.)
    openclaw_token = EncryptedCharField(max_length=500, blank=True, default='', verbose_name="OpenClaw API Token",
                                        help_text="Token fuer die OpenClaw HTTP API (openclaw config get gateway.auth.token)")

    # Dynamisches Push-Intervall (Sekunden) - wird bei aktivem Chat auf 3s gesetzt
    push_interval_override = models.IntegerField(null=True, blank=True, verbose_name="Push-Intervall Override (s)")

    # System-Monitoring
    cpu_percent = models.FloatField(null=True, blank=True, verbose_name="CPU %")
    ram_used_mb = models.IntegerField(null=True, blank=True, verbose_name="RAM (MB)")
    ram_total_mb = models.IntegerField(null=True, blank=True, verbose_name="RAM Total (MB)")
    disk_used_gb = models.FloatField(null=True, blank=True, verbose_name="Disk Used (GB)")
    disk_total_gb = models.FloatField(null=True, blank=True, verbose_name="Disk Total (GB)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Clawdbot Verbindung"
        verbose_name_plural = "Clawdbot Verbindungen"
        ordering = ['-is_active', '-last_seen']

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Project(models.Model):
    """Projekt das von Clawdbot bearbeitet wird"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200, verbose_name="Projektname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('planned', 'Geplant'),
        ('completed', 'Abgeschlossen'),
        ('archived', 'Archiviert'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    
    PRIORITY_CHOICES = [
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Priorität")
    
    color = models.CharField(max_length=7, default='#6c757d', verbose_name="Farbe")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon", help_text="Emoji oder Bootstrap Icon")
    tags = models.JSONField(default=list, blank=True, verbose_name="Tags")
    
    # Verknüpfung zu Memory-Dateien
    memory_path = models.CharField(max_length=500, blank=True, verbose_name="Memory-Pfad", 
                                   help_text="Pfad zur .md Datei (relativ zum Workspace)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projekt"
        verbose_name_plural = "Projekte"
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class ProjectMemory(models.Model):
    """Memory-Eintrag zu einem Projekt"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memories')
    content = models.TextField(verbose_name="Inhalt")
    source = models.CharField(max_length=255, blank=True, verbose_name="Quelle", 
                             help_text="z.B. memory/2026-02-09.md")
    
    ENTRY_TYPE_CHOICES = [
        ('note', 'Notiz'),
        ('decision', 'Entscheidung'),
        ('task', 'Aufgabe'),
        ('idea', 'Idee'),
        ('issue', 'Problem'),
        ('solution', 'Lösung'),
    ]
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPE_CHOICES, default='note', verbose_name="Typ")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projekt-Memory"
        verbose_name_plural = "Projekt-Memories"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name}: {self.content[:50]}..."


class Conversation(models.Model):
    """Gespeicherte Konversation mit Clawdbot"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='conversations')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    
    session_key = models.CharField(max_length=255, verbose_name="Session Key")
    title = models.CharField(max_length=500, blank=True, verbose_name="Titel")
    summary = models.TextField(blank=True, verbose_name="Zusammenfassung")
    
    # Konversationsdaten
    messages = models.JSONField(default=list, verbose_name="Nachrichten")
    message_count = models.IntegerField(default=0, verbose_name="Anzahl Nachrichten")
    
    # Tokens & Kosten
    total_tokens = models.IntegerField(default=0, verbose_name="Tokens gesamt")
    total_cost = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name="Kosten ($)")
    
    channel = models.CharField(max_length=50, blank=True, verbose_name="Kanal", help_text="telegram, webchat, etc.")
    
    started_at = models.DateTimeField(verbose_name="Gestartet")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Beendet")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Konversation"
        verbose_name_plural = "Konversationen"
        ordering = ['-started_at']

    def __str__(self):
        return self.title or f"Konversation {self.session_key[:8]}..."


class ScheduledTask(models.Model):
    """Geplante Aufgabe / Cron-Job"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='scheduled_tasks')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_tasks')
    
    cron_job_id = models.CharField(max_length=100, verbose_name="Cron Job ID", help_text="ID vom Clawdbot")
    name = models.CharField(max_length=200, verbose_name="Name")
    schedule = models.CharField(max_length=100, verbose_name="Schedule", help_text="Cron-Expression oder Beschreibung")
    text = models.TextField(verbose_name="Aufgabentext")
    
    is_enabled = models.BooleanField(default=True, verbose_name="Aktiviert")
    last_run = models.DateTimeField(null=True, blank=True, verbose_name="Zuletzt ausgeführt")
    next_run = models.DateTimeField(null=True, blank=True, verbose_name="Nächste Ausführung")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Geplante Aufgabe"
        verbose_name_plural = "Geplante Aufgaben"
        ordering = ['next_run']

    def __str__(self):
        return self.name


class MemoryFile(models.Model):
    """Memory-Datei (.md) vom Clawdbot-Workspace"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='memory_files')
    
    path = models.CharField(max_length=500, verbose_name="Dateipfad")
    filename = models.CharField(max_length=255, verbose_name="Dateiname")
    content = models.TextField(verbose_name="Inhalt")
    
    file_type = models.CharField(max_length=50, default='markdown', verbose_name="Dateityp")
    size_bytes = models.IntegerField(default=0, verbose_name="Größe (Bytes)")
    
    last_synced = models.DateTimeField(auto_now=True, verbose_name="Zuletzt synchronisiert")
    remote_modified = models.DateTimeField(null=True, blank=True, verbose_name="Remote geändert")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Memory-Datei"
        verbose_name_plural = "Memory-Dateien"
        ordering = ['-last_synced']
        unique_together = ['connection', 'path']

    def __str__(self):
        return self.filename


class Integration(models.Model):
    """Konfigurierte Integration/Zugang"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='integrations')
    
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
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="Kategorie")
    
    name = models.CharField(max_length=100, verbose_name="Name", help_text="z.B. 'GitHub', 'Zoho Mail'")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon")
    
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('inactive', 'Inaktiv'),
        ('error', 'Fehler'),
        ('pending', 'Ausstehend'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    
    config = models.JSONField(default=dict, blank=True, verbose_name="Konfiguration")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    
    last_verified = models.DateTimeField(null=True, blank=True, verbose_name="Zuletzt geprüft")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Integration"
        verbose_name_plural = "Integrationen"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Skill(models.Model):
    """Erkannte Faehigkeit/Technologie auf dem verbundenen Rechner"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='skills')

    name = models.CharField(max_length=100, verbose_name="Name")
    CATEGORY_CHOICES = [
        ('language', 'Programmiersprache'),
        ('tool', 'Tool'),
        ('framework', 'Framework'),
        ('runtime', 'Runtime'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='tool', verbose_name="Kategorie")
    version = models.CharField(max_length=100, blank=True, verbose_name="Version")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon")

    detected_at = models.DateTimeField(auto_now=True, verbose_name="Erkannt am")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Skill"
        verbose_name_plural = "Skills"
        unique_together = ['connection', 'name']
        ordering = ['category', 'name']

    def __str__(self):
        v = f" {self.version}" if self.version else ""
        return f"{self.name}{v}"


class ClawboardChat(models.Model):
    """KI-Chat im Clawboard"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clawboard_chats')

    title = models.CharField(max_length=200, blank=True, verbose_name="Titel")

    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('deepseek', 'DeepSeek'),
        ('gemini', 'Google Gemini'),
        ('gateway', 'Gateway'),
    ]
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='gateway', verbose_name="Provider")
    model_name = models.CharField(max_length=100, verbose_name="Modell")

    CHAT_MODE_CHOICES = [
        ('gateway', 'Gateway (OpenClaw)'),
        ('direct', 'Direkt (API Key)'),
    ]
    chat_mode = models.CharField(max_length=10, choices=CHAT_MODE_CHOICES, default='gateway', verbose_name="Chat-Modus")

    # Nachrichten als JSON: [{"role": "user"|"assistant"|"system", "content": "...", "timestamp": "..."}]
    messages = models.JSONField(default=list, verbose_name="Nachrichten")
    message_count = models.IntegerField(default=0, verbose_name="Anzahl Nachrichten")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KI-Chat"
        verbose_name_plural = "KI-Chats"
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Chat {self.pk}"


class ChatMessageRequest(models.Model):
    """Queue fuer Chat-Nachrichten die ueber den Gateway geroutet werden"""
    chat = models.ForeignKey(ClawboardChat, on_delete=models.CASCADE, related_name='gateway_requests')
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='chat_requests')

    STATUS_CHOICES = [
        ('queued', 'In Warteschlange'),
        ('processing', 'Wird verarbeitet'),
        ('completed', 'Abgeschlossen'),
        ('error', 'Fehler'),
        ('timeout', 'Timeout'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued', verbose_name="Status")

    # Die vollstaendige Nachrichten-Historie fuer den AI-Call
    request_messages = models.JSONField(verbose_name="Request Messages")
    model_identifier = models.CharField(max_length=200, verbose_name="Modell-Identifier")

    # Antwort vom Gateway
    response_content = models.TextField(blank=True, verbose_name="Antwort")
    error_message = models.TextField(blank=True, verbose_name="Fehlermeldung")

    timeout_seconds = models.IntegerField(default=120, verbose_name="Timeout (s)")

    created_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name="Abgeholt am")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Abgeschlossen am")

    class Meta:
        verbose_name = "Chat-Request"
        verbose_name_plural = "Chat-Requests"
        ordering = ['-created_at']

    def __str__(self):
        return f"Request {self.pk} ({self.status}) - {self.model_identifier}"


class GatewayModelCache(models.Model):
    """Verfuegbare KI-Modelle vom OpenClaw Gateway"""
    connection = models.ForeignKey(ClawdbotConnection, on_delete=models.CASCADE, related_name='gateway_models')

    model_id = models.CharField(max_length=200, verbose_name="Modell-ID")
    model_name = models.CharField(max_length=200, verbose_name="Anzeigename")
    provider = models.CharField(max_length=100, blank=True, verbose_name="Provider")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_available = models.BooleanField(default=True, verbose_name="Verfuegbar")

    last_seen = models.DateTimeField(auto_now=True, verbose_name="Zuletzt gesehen")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gateway-Modell"
        verbose_name_plural = "Gateway-Modelle"
        unique_together = ['connection', 'model_id']
        ordering = ['provider', 'model_name']

    def __str__(self):
        return f"{self.model_name} ({self.provider})"

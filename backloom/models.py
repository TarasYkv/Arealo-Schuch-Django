import hashlib
import uuid
from urllib.parse import urlparse

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

# Encrypted field fuer Passwoerter (z.B. IMAP-Password im NaturmacherProfile)
from encrypted_model_fields.fields import EncryptedCharField as _EncryptedCharField

User = get_user_model()


class BacklinkCategory(models.TextChoices):
    """Kategorien für Backlink-Quellen"""
    FORUM = 'forum', 'Forum'
    DIRECTORY = 'directory', 'Verzeichnis'
    GUEST_POST = 'guest_post', 'Gastbeitrag'
    COMMENT = 'comment', 'Kommentar'
    SOCIAL = 'social', 'Social Media'
    VIDEO = 'video', 'Video'
    QA = 'qa', 'Frage & Antwort'
    PROFILE = 'profile', 'Profil'
    WIKI = 'wiki', 'Wiki'
    NEWS = 'news', 'News/Presse'
    OTHER = 'other', 'Sonstiges'


class SourceType(models.TextChoices):
    """Quelltypen (Suchmaschinen/Plattformen)"""
    GOOGLE = 'google', 'Google'
    BING = 'bing', 'Bing'
    DUCKDUCKGO = 'duckduckgo', 'DuckDuckGo'
    ECOSIA = 'ecosia', 'Ecosia'
    YAHOO = 'yahoo', 'Yahoo'
    REDDIT = 'reddit', 'Reddit'
    YOUTUBE = 'youtube', 'YouTube'
    TIKTOK = 'tiktok', 'TikTok'
    QUORA = 'quora', 'Quora'
    PINTEREST = 'pinterest', 'Pinterest'
    MEDIUM = 'medium', 'Medium'
    MANUAL = 'manual', 'Manuell'


class SearchQuery(models.Model):
    """Vordefinierte Suchbegriffe für Backlink-Recherche"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.CharField(max_length=255, verbose_name='Suchbegriff')
    category = models.CharField(
        max_length=20,
        choices=BacklinkCategory.choices,
        default=BacklinkCategory.OTHER,
        verbose_name='Kategorie'
    )
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    priority = models.PositiveIntegerField(default=5, verbose_name='Priorität (1-10)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Suchbegriff'
        verbose_name_plural = 'Suchbegriffe'
        ordering = ['-priority', 'query']

    def __str__(self):
        return f"{self.query} ({self.get_category_display()})"


class BacklinkSource(models.Model):
    """Gefundene Backlink-Quelle (Feed-Eintrag)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # URL-Informationen
    url = models.TextField(verbose_name='URL')  # TextField für lange URLs
    url_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='URL-Hash',
        help_text='SHA256-Hash der URL für Duplikat-Erkennung'
    )
    domain = models.CharField(max_length=255, verbose_name='Domain')
    title = models.CharField(max_length=500, blank=True, verbose_name='Seitentitel')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    favicon_url = models.URLField(max_length=500, blank=True, verbose_name='Favicon URL')

    # Kategorisierung
    category = models.CharField(
        max_length=20,
        choices=BacklinkCategory.choices,
        default=BacklinkCategory.OTHER,
        verbose_name='Kategorie'
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.GOOGLE,
        verbose_name='Gefunden über'
    )
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='found_sources',
        verbose_name='Suchbegriff'
    )

    # Bewertung
    quality_score = models.PositiveIntegerField(
        default=50,
        verbose_name='Qualitätsbewertung (0-100)'
    )
    domain_authority = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Domain Authority'
    )

    # Status
    is_processed = models.BooleanField(
        default=False,
        verbose_name='Bearbeitet'
    )
    is_successful = models.BooleanField(
        default=False,
        verbose_name='Backlink erstellt'
    )
    is_rejected = models.BooleanField(
        default=False,
        verbose_name='Abgelehnt/Ungeeignet'
    )
    notes = models.TextField(blank=True, verbose_name='Notizen')

    # Submission-Pipeline-Felder (Phase 1)
    captcha_type = models.CharField(
        max_length=24, blank=True, default='',
        verbose_name='Erkannter Captcha-Typ',
        help_text='Wird beim ersten Bot-Lauf gesetzt (recaptcha_v2, hcaptcha, ...)',
    )
    requires_account = models.BooleanField(
        null=True, blank=True,
        verbose_name='Erfordert Account-Anlage?',
        help_text='Null = unbekannt, True/False = nach erstem Lauf bekannt',
    )
    form_schema = models.JSONField(
        default=dict, blank=True,
        verbose_name='Gelerntes Formular-Schema',
        help_text='LLM/Bot speichert hier Selektoren-Mapping für deterministisches Replay',
    )
    submission_blocked_until = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Cooldown bis',
        help_text='Solange darf der Bot diese Source nicht erneut anfassen',
    )

    # Zeitstempel
    first_found = models.DateTimeField(
        default=timezone.now,
        verbose_name='Erstmals gefunden'
    )
    last_found = models.DateTimeField(
        default=timezone.now,
        verbose_name='Zuletzt gefunden'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Backlink-Quelle'
        verbose_name_plural = 'Backlink-Quellen'
        ordering = ['-last_found']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['category']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['-last_found']),
            models.Index(fields=['-quality_score']),
            models.Index(fields=['url_hash']),
        ]

    def __str__(self):
        return f"{self.domain} - {self.title[:50] if self.title else 'Kein Titel'}"

    def save(self, *args, **kwargs):
        # URL-Hash für Duplikat-Erkennung generieren
        if self.url and not self.url_hash:
            self.url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()

        # Domain automatisch extrahieren
        if self.url and not self.domain:
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.replace('www.', '')

        # Favicon URL generieren falls nicht vorhanden
        if not self.favicon_url and self.domain:
            self.favicon_url = f"https://www.google.com/s2/favicons?domain={self.domain}&sz=32"

        super().save(*args, **kwargs)

    @staticmethod
    def get_url_hash(url: str) -> str:
        """Generiert SHA256-Hash für eine URL"""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def get_absolute_url(self):
        return reverse('backloom:source_detail', kwargs={'pk': self.pk})

    @property
    def age_days(self):
        """Alter des Eintrags in Tagen"""
        return (timezone.now() - self.first_found).days

    @property
    def is_expired(self):
        """Prüft ob Eintrag älter als 12 Monate ist"""
        return self.last_found < timezone.now() - timedelta(days=365)

    @property
    def quality_label(self):
        """Qualitätslabel basierend auf Score"""
        if self.quality_score >= 80:
            return 'Exzellent'
        elif self.quality_score >= 60:
            return 'Gut'
        elif self.quality_score >= 40:
            return 'Mittel'
        elif self.quality_score >= 20:
            return 'Niedrig'
        return 'Sehr niedrig'

    @property
    def quality_color(self):
        """Bootstrap-Farbklasse basierend auf Score"""
        if self.quality_score >= 80:
            return 'success'
        elif self.quality_score >= 60:
            return 'info'
        elif self.quality_score >= 40:
            return 'warning'
        return 'danger'


class BacklinkSearchStatus(models.TextChoices):
    """Status einer Suche"""
    PENDING = 'pending', 'Ausstehend'
    RUNNING = 'running', 'Läuft'
    COMPLETED = 'completed', 'Abgeschlossen'
    FAILED = 'failed', 'Fehlgeschlagen'
    CANCELLED = 'cancelled', 'Abgebrochen'


class BacklinkSearch(models.Model):
    """Protokoll einer Backlink-Suche"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='backloom_searches',
        verbose_name='Ausgelöst von'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=BacklinkSearchStatus.choices,
        default=BacklinkSearchStatus.PENDING,
        verbose_name='Status'
    )

    # Zeitstempel
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Gestartet am')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Abgeschlossen am')

    # Statistiken
    sources_found = models.PositiveIntegerField(default=0, verbose_name='Gefundene Quellen')
    new_sources = models.PositiveIntegerField(default=0, verbose_name='Neue Quellen')
    updated_sources = models.PositiveIntegerField(default=0, verbose_name='Aktualisierte Quellen')

    # Fehlerprotokoll
    error_log = models.TextField(blank=True, verbose_name='Fehlerprotokoll')
    progress_log = models.TextField(blank=True, verbose_name='Fortschrittsprotokoll')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        verbose_name = 'Backlink-Suche'
        verbose_name_plural = 'Backlink-Suchen'
        ordering = ['-created_at']

    def __str__(self):
        return f"Suche vom {self.created_at.strftime('%d.%m.%Y %H:%M')} - {self.get_status_display()}"

    @property
    def duration(self):
        """Dauer der Suche in Sekunden"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def duration_formatted(self):
        """Formatierte Dauer"""
        duration = self.duration
        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes}m {seconds}s"
        return "-"

    def start(self):
        """Suche starten"""
        self.status = BacklinkSearchStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def complete(self, sources_found=0, new_sources=0, updated_sources=0):
        """Suche abschließen"""
        self.status = BacklinkSearchStatus.COMPLETED
        self.completed_at = timezone.now()
        self.sources_found = sources_found
        self.new_sources = new_sources
        self.updated_sources = updated_sources
        self.save(update_fields=[
            'status', 'completed_at', 'sources_found',
            'new_sources', 'updated_sources'
        ])

    def fail(self, error_message):
        """Suche als fehlgeschlagen markieren"""
        self.status = BacklinkSearchStatus.FAILED
        self.completed_at = timezone.now()
        self.error_log = error_message
        self.save(update_fields=['status', 'completed_at', 'error_log'])

    def log_progress(self, message):
        """Fortschritt protokollieren"""
        timestamp = timezone.now().strftime('%H:%M:%S')
        self.progress_log += f"[{timestamp}] {message}\n"
        self.save(update_fields=['progress_log'])


# ===========================================================================
# Phase 1: Submission-Pipeline (Bot, Bios, Profil)
# ===========================================================================


class CaptchaType(models.TextChoices):
    """Erkannter Captcha-Typ einer Source"""
    NONE = 'none', 'Kein Captcha'
    RECAPTCHA_V2 = 'recaptcha_v2', 'reCAPTCHA v2'
    RECAPTCHA_V3 = 'recaptcha_v3', 'reCAPTCHA v3'
    HCAPTCHA = 'hcaptcha', 'hCaptcha'
    TURNSTILE = 'turnstile', 'Cloudflare Turnstile'
    CLOUDFLARE = 'cloudflare', 'Cloudflare Challenge'
    CUSTOM = 'custom', 'Custom (Math/Image)'
    UNKNOWN = 'unknown', 'Unbekannt'


class NaturmacherProfile(models.Model):
    """Zentrale Firmen-/Profil-Daten, die der Bot beim Ausfüllen verwendet.

    Pro Workloom-User eine Instanz (für Multi-Tenant-Fähigkeit).
    Felder analog zu typischen Verzeichnis-Anmeldeformularen.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='backloom_profile',
        verbose_name='Workloom-User',
    )
    # Firmenkennzeichen
    firma = models.CharField(max_length=255, verbose_name='Firmenname')
    inhaber = models.CharField(max_length=255, blank=True, verbose_name='Inhaber/Geschäftsführer')
    vorname = models.CharField(max_length=100, blank=True, verbose_name='Vorname')
    nachname = models.CharField(max_length=100, blank=True, verbose_name='Nachname')
    rechtsform = models.CharField(max_length=100, blank=True, verbose_name='Rechtsform',
                                   help_text='z.B. GbR, GmbH, e.K., Einzelunternehmen')
    ust_id = models.CharField(max_length=32, blank=True, verbose_name='USt-ID')
    handelsregister = models.CharField(max_length=64, blank=True, verbose_name='Handelsregister')

    # Kontakt
    website = models.URLField(verbose_name='Website')
    email = models.EmailField(verbose_name='Kontakt-E-Mail (für Registrierungen)')
    email_shop = models.EmailField(blank=True, verbose_name='Shop-E-Mail (öffentlich)')
    telefon = models.CharField(max_length=64, blank=True, verbose_name='Telefon')

    # Adresse
    strasse = models.CharField(max_length=255, blank=True, verbose_name='Straße + Hausnummer')
    plz = models.CharField(max_length=16, blank=True, verbose_name='PLZ')
    ort = models.CharField(max_length=128, blank=True, verbose_name='Ort')
    land = models.CharField(max_length=64, default='Deutschland', verbose_name='Land')

    # Kategorisierung
    kategorie = models.CharField(max_length=255, blank=True, verbose_name='Default-Kategorie',
                                  help_text='z.B. "Shopping / Geschenke / Personalisiert"')
    keywords = models.TextField(blank=True, verbose_name='Keywords/Tags',
                                 help_text='Komma-getrennt für Verzeichnisse')

    # Default-Login-Daten (für Account-basierte Sites)
    default_username = models.CharField(max_length=128, blank=True, verbose_name='Standard-Username',
                                          help_text='Wird verwendet wenn Site nicht "Email als Username" akzeptiert')
    # Achtung: Klartext nur weil Verzeichnis-Accounts Throwaway-Niveau haben.
    # Bei sensiblen Logins separat erfassen.
    default_password = models.CharField(max_length=255, blank=True, verbose_name='Standard-Passwort')

    # IMAP-Zugang fuer Email-Bestaetigungs-Workflow (Phase 4.4)
    # Der Bot loggt nach Registrierung in dieses Postfach ein und sucht
    # die Confirmation-Mail mit "klicken Sie auf den folgenden Link..."
    imap_host = models.CharField(max_length=128, blank=True, default='imappro.zoho.eu',
                                  verbose_name='IMAP-Server')
    imap_port = models.PositiveIntegerField(default=993, verbose_name='IMAP-Port (SSL)')
    imap_username = models.CharField(max_length=255, blank=True,
                                      verbose_name='IMAP-Username (=Email)',
                                      help_text='Wenn leer: profile.email')
    # Encrypted (analog zu CustomUser-API-Keys, EncryptedCharField vom encrypted_model_fields-Paket).
    imap_password = _EncryptedCharField(
        max_length=255, blank=True, null=True, verbose_name='IMAP-Passwort',
        help_text='App-Passwort von Zoho/etc. — niemals Account-Hauptpasswort verwenden',
    )

    # Beschreibungen sind in BioVariant ausgelagert (Variation gegen Spam-Pattern)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Naturmacher-Profil'
        verbose_name_plural = 'Naturmacher-Profile'

    def __str__(self):
        return f'{self.firma} ({self.user.username})'

    def to_field_map(self) -> dict:
        """Liefert ein Dict mit allen relevanten Feldern, die der Bot in Forms eintragen kann.

        Keys sind die kanonischen Feldnamen, die das LLM bei der Form-Erkennung
        zurückgibt (z.B. "company_name", "email", "phone").
        """
        return {
            'company_name': self.firma,
            'owner_name': self.inhaber or f'{self.vorname} {self.nachname}'.strip(),
            'first_name': self.vorname,
            'last_name': self.nachname,
            'website': self.website,
            'email': self.email,
            'email_shop': self.email_shop,
            'phone': self.telefon,
            'street': self.strasse,
            'postal_code': self.plz,
            'city': self.ort,
            'country': self.land,
            'vat_id': self.ust_id,
            'category': self.kategorie,
            'keywords': self.keywords,
            'username': self.default_username or self.email,
            'password': self.default_password,
        }


class BioVariant(models.Model):
    """Beschreibungstext-Varianten für Anti-Spam-Pattern-Diversität.

    Pro Submission picked der Bot zufällig eine Variante in passender Länge.
    Längen-Buckets entsprechen typischen Verzeichnis-Limits (Twitter-/IG-Style 160,
    Standard-Verzeichnis 300, Lange Beschreibung 500 Zeichen).
    """
    LENGTH_SHORT = 160
    LENGTH_MEDIUM = 300
    LENGTH_LONG = 500
    LENGTH_CHOICES = [
        (LENGTH_SHORT, 'Kurz (≤160)'),
        (LENGTH_MEDIUM, 'Mittel (≤300)'),
        (LENGTH_LONG, 'Lang (≤500)'),
    ]

    profile = models.ForeignKey(
        NaturmacherProfile, on_delete=models.CASCADE,
        related_name='bio_variants',
        verbose_name='Profil',
    )
    text = models.TextField(verbose_name='Bio-Text')
    length_bucket = models.PositiveIntegerField(
        choices=LENGTH_CHOICES, default=LENGTH_MEDIUM, verbose_name='Längen-Kategorie',
    )
    use_count = models.PositiveIntegerField(default=0, verbose_name='Anzahl Verwendungen')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Zuletzt verwendet')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bio-Variante'
        verbose_name_plural = 'Bio-Varianten'
        ordering = ['length_bucket', 'use_count', 'created_at']
        indexes = [
            models.Index(fields=['profile', 'length_bucket', 'is_active']),
        ]

    def __str__(self):
        return f'[{self.length_bucket}] {self.text[:60]}…'

    def mark_used(self):
        self.use_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['use_count', 'last_used_at'])


class SubmissionAttemptStatus(models.TextChoices):
    QUEUED = 'queued', 'In Warteschlange'
    RUNNING = 'running', 'Läuft'
    NEEDS_MANUAL = 'needs_manual', 'Manuell eingreifen'
    PENDING_VERIFY = 'pending_verify', '🔍 Verifiziere Link'
    SUCCESS = 'success', '✅ Verifiziert (Backlink live)'
    FAILED_CAPTCHA = 'failed_captcha', 'Captcha-Fehler'
    FAILED_OTHER = 'failed_other', 'Fehler'
    FAILED_NO_LINK = 'failed_no_link', '❌ Kein Backlink gefunden'
    ALREADY_REGISTERED = 'already_registered', 'ℹ️ Bereits registriert'
    SKIPPED = 'skipped', 'Übersprungen'


class ControlledBy(models.TextChoices):
    """Wer steuert gerade den Browser-Tab eines aktiven Submissions-Attempts."""
    BOT = 'bot', '🤖 Bot'
    HUMAN = 'human', '👤 Mensch'


class SubmissionAttempt(models.Model):
    """Ein einzelner Bot-Lauf für eine Source.

    Eine BacklinkSource kann mehrere Attempts haben (Retry/manuelle Wiederholung).
    Jeder Attempt protokolliert: Schritte, Screenshots, finalen Backlink-URL,
    Verify-Status, Kosten.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        BacklinkSource, on_delete=models.CASCADE,
        related_name='submission_attempts',
        verbose_name='Source',
    )
    profile = models.ForeignKey(
        NaturmacherProfile, on_delete=models.PROTECT,
        related_name='submissions',
        verbose_name='Profil',
    )
    bio_variant = models.ForeignKey(
        BioVariant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submissions',
        verbose_name='Verwendete Bio',
    )

    # Status
    status = models.CharField(
        max_length=24, choices=SubmissionAttemptStatus.choices,
        default=SubmissionAttemptStatus.QUEUED, verbose_name='Status',
    )
    controlled_by = models.CharField(
        max_length=8, choices=ControlledBy.choices,
        default=ControlledBy.BOT,
        verbose_name='Aktive Steuerung',
        help_text='Wer steuert gerade den Browser. BOT = Agent macht Schritte. '
                  'HUMAN = User hat per Takeover die Steuerung uebernommen.',
    )
    control_taken_at = models.DateTimeField(null=True, blank=True,
                                              verbose_name='Steuerung uebernommen am')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Gestartet')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Beendet')

    # Resultate
    backlink_url = models.URLField(max_length=600, blank=True,
                                    verbose_name='Erstellter Backlink (URL der Profilseite)')
    is_dofollow = models.BooleanField(null=True, blank=True, verbose_name='DoFollow?')
    is_verified_live = models.BooleanField(null=True, blank=True, verbose_name='Verifiziert live?')
    last_verified_at = models.DateTimeField(null=True, blank=True)

    # Browser-Container
    container_id = models.CharField(max_length=64, blank=True,
                                     verbose_name='Docker-Container-ID',
                                     help_text='Für Live-View')
    novnc_url = models.URLField(max_length=400, blank=True,
                                 verbose_name='noVNC Live-View URL')

    # Anchor-Text (was als Linktext verwendet wurde)
    anchor_text_used = models.CharField(max_length=255, blank=True, verbose_name='Anchor-Text')

    # Step-Log und Screenshots
    step_log = models.JSONField(default=list, blank=True,
                                 verbose_name='Schritt-Log',
                                 help_text='Liste von {ts, msg, screenshot_url}')
    error_message = models.TextField(blank=True, verbose_name='Fehlermeldung')
    captcha_solver_used = models.CharField(max_length=32, blank=True,
                                            verbose_name='Captcha-Solver',
                                            help_text='flaresolverr/buster/capsolver/2captcha/manual')

    # Kosten
    cost_eur = models.DecimalField(max_digits=8, decimal_places=4, default=0,
                                    verbose_name='Kosten (€)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Submission-Attempt'
        verbose_name_plural = 'Submission-Attempts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.source.domain} | {self.get_status_display()} | {self.created_at:%d.%m. %H:%M}'

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    def add_step(self, message: str, screenshot_url: str = '', level: str = 'info'):
        """Fügt einen Schritt zum Log hinzu (UI-Stream nutzt das)."""
        entry = {
            'ts': timezone.now().isoformat(),
            'level': level,
            'msg': message,
        }
        if screenshot_url:
            entry['screenshot'] = screenshot_url
        log = list(self.step_log or [])
        log.append(entry)
        self.step_log = log
        self.save(update_fields=['step_log', 'updated_at'])

    @property
    def reason_short(self) -> str:
        """Kurzbegruendung warum der Attempt im aktuellen Status ist.

        Bevorzugt:
        - error_message wenn gesetzt
        - sonst: letzte Step-Log-Zeile mit level=warn oder error
        - sonst: letzte Step-Log-Zeile (egal welcher Level)
        """
        if self.error_message:
            return self.error_message[:200]
        log = self.step_log or []
        # Suche rueckwaerts nach warn/error
        for entry in reversed(log):
            if entry.get('level') in ('warn', 'error'):
                return entry.get('msg', '')[:200]
        # Fallback: letzte info-Zeile
        if log:
            return log[-1].get('msg', '')[:200]
        return ''

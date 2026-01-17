import hashlib
import uuid
from urllib.parse import urlparse

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

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
    QUORA = 'quora', 'Quora'
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

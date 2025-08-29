from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class LoomAdsSettings(models.Model):
    """Global LoomAds settings and app-specific controls"""
    
    # Global settings
    enable_tracking = models.BooleanField(default=True, verbose_name='Tracking aktivieren')
    enable_targeting = models.BooleanField(default=True, verbose_name='Targeting aktivieren')
    enable_scheduling = models.BooleanField(default=True, verbose_name='Zeitplanung aktivieren')
    default_daily_limit = models.IntegerField(null=True, blank=True, verbose_name='Standard tägliches Limit')
    default_weight = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    # App-specific zone controls
    enable_header_zones = models.JSONField(default=dict, verbose_name='Header-Zonen pro App')
    enable_footer_zones = models.JSONField(default=dict, verbose_name='Footer-Zonen pro App')
    enable_sidebar_zones = models.JSONField(default=dict, verbose_name='Sidebar-Zonen pro App')
    enable_infeed_zones = models.JSONField(default=dict, verbose_name='In-Feed-Zonen pro App')
    enable_modal_zones = models.JSONField(default=dict, verbose_name='Modal-Zonen pro App')
    
    # Global zone controls
    global_header_enabled = models.BooleanField(default=True, verbose_name='Header-Zonen global')
    global_footer_enabled = models.BooleanField(default=True, verbose_name='Footer-Zonen global')
    global_sidebar_enabled = models.BooleanField(default=True, verbose_name='Sidebar-Zonen global')
    global_infeed_enabled = models.BooleanField(default=True, verbose_name='In-Feed-Zonen global')
    global_modal_enabled = models.BooleanField(default=True, verbose_name='Modal-Zonen global')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'LoomAds Einstellungen'
        verbose_name_plural = 'LoomAds Einstellungen'
    
    def __str__(self):
        return 'LoomAds Einstellungen'
    
    @classmethod
    def get_settings(cls):
        """Get or create LoomAds settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    def is_zone_enabled(self, zone_type, app_name=None):
        """Check if a zone type is enabled for a specific app"""
        # Check global setting first
        global_enabled = getattr(self, f'global_{zone_type}_enabled', True)
        if not global_enabled:
            return False
        
        # If no app specified, return global setting
        if not app_name:
            return global_enabled
        
        # Check app-specific setting
        app_settings = getattr(self, f'enable_{zone_type}_zones', {})
        return app_settings.get(app_name, True)  # Default to enabled
    
    def set_zone_enabled(self, zone_type, app_name, enabled):
        """Set zone enabled status for a specific app"""
        field_name = f'enable_{zone_type}_zones'
        app_settings = getattr(self, field_name, {})
        app_settings[app_name] = enabled
        setattr(self, field_name, app_settings)
        self.save()


class Campaign(models.Model):
    """Werbekampagne"""
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('active', 'Aktiv'),
        ('paused', 'Pausiert'),
        ('completed', 'Abgeschlossen'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='Kampagnenname')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ad_campaigns')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateTimeField(verbose_name='Startdatum')
    end_date = models.DateTimeField(verbose_name='Enddatum')
    daily_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tägliches Impression-Limit',
        help_text='Maximale Anzahl der Impressions pro Tag (leer = unbegrenzt)'
    )
    total_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Gesamt Impression-Limit',
        help_text='Maximale Anzahl der Impressions insgesamt (leer = unbegrenzt)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Kampagne'
        verbose_name_plural = 'Kampagnen'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )
    
    def get_total_impressions(self):
        """Get total impressions for all ads in this campaign"""
        return self.advertisements.aggregate(total=models.Sum('impressions_count'))['total'] or 0
    
    def get_total_clicks(self):
        """Get total clicks for all ads in this campaign"""
        return self.advertisements.aggregate(total=models.Sum('clicks_count'))['total'] or 0
    
    def get_ctr(self):
        """Get Click-Through Rate for this campaign"""
        impressions = self.get_total_impressions()
        clicks = self.get_total_clicks()
        if impressions > 0:
            return (clicks / impressions) * 100
        return 0


class AdZone(models.Model):
    """Werbebereich auf der Website"""
    ZONE_TYPES = [
        ('header', 'Header Banner'),
        ('footer', 'Footer Banner'),
        ('sidebar', 'Seitenleiste'),
        ('in_feed', 'In-Feed'),
        ('modal', 'Modal/Pop-up'),
        ('video_preroll', 'Video Pre-Roll'),
        ('video_overlay', 'Video Overlay'),
        ('video_popup', 'Video Pop-up (unten rechts)'),
        ('content_card', 'Content Card'),
        ('notification', 'Benachrichtigung'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='Zone Code')
    name = models.CharField(max_length=200, verbose_name='Zone Name')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    zone_type = models.CharField(max_length=30, choices=ZONE_TYPES)
    width = models.IntegerField(verbose_name='Breite (px)')
    height = models.IntegerField(verbose_name='Höhe (px)')
    max_ads = models.IntegerField(
        default=1,
        verbose_name='Maximale Anzahl Anzeigen',
        help_text='Wie viele Anzeigen können gleichzeitig in dieser Zone angezeigt werden'
    )
    # Video-Popup spezifische Einstellungen
    popup_delay = models.IntegerField(
        default=5, 
        verbose_name='Popup Verzögerung (Sekunden)',
        help_text='Nach wie vielen Sekunden soll das Video-Popup erscheinen?'
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    app_restriction = models.CharField(
        max_length=100, blank=True,
        verbose_name='App-Beschränkung',
        help_text='Nur in dieser App anzeigen (leer = überall)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Werbezone'
        verbose_name_plural = 'Werbezonen'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Advertisement(models.Model):
    """Einzelne Werbeanzeige"""
    AD_TYPES = [
        ('image', 'Bild'),
        ('html', 'HTML/Rich Content'),
        ('video', 'Video'),
        ('text', 'Text'),
    ]
    
    TARGET_CHOICES = [
        ('_self', 'Gleiche Seite'),
        ('_blank', 'Neues Fenster'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='advertisements')
    name = models.CharField(max_length=200, verbose_name='Anzeigenname')
    
    # Content
    ad_type = models.CharField(max_length=20, choices=AD_TYPES, default='image')
    image = models.ImageField(upload_to='loomads/images/%Y/%m/', blank=True, null=True, verbose_name='Bild')
    video_url = models.URLField(blank=True, verbose_name='Video URL')
    video_with_audio = models.BooleanField(default=True, verbose_name='Video mit Ton', help_text='Soll das Video mit oder ohne Ton abgespielt werden?')
    title = models.CharField(max_length=200, blank=True, verbose_name='Titel')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    html_content = models.TextField(blank=True, verbose_name='HTML Inhalt')
    
    # Link settings
    target_url = models.URLField(verbose_name='Ziel-URL')
    target_type = models.CharField(
        max_length=10,
        choices=TARGET_CHOICES,
        default='_blank',
        verbose_name='Link öffnen in'
    )
    
    # Display settings
    zones = models.ManyToManyField(AdZone, related_name='advertisements', verbose_name='Werbezonen')
    weight = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Gewichtung',
        help_text='Höhere Gewichtung = häufigere Anzeige (1-10)'
    )
    
    # Tracking
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    impressions_count = models.IntegerField(default=0, verbose_name='Impressions')
    clicks_count = models.IntegerField(default=0, verbose_name='Klicks')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Werbeanzeige'
        verbose_name_plural = 'Werbeanzeigen'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.campaign.name})"
    
    @property
    def ctr(self):
        """Click-Through-Rate berechnen"""
        if self.impressions_count > 0:
            return (self.clicks_count / self.impressions_count) * 100
        return 0
    
    def get_ctr(self):
        """Get Click-Through Rate for templates"""
        return self.ctr


class AdPlacement(models.Model):
    """Platzierung einer Anzeige in einer Zone"""
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE)
    zone = models.ForeignKey(AdZone, on_delete=models.CASCADE)
    priority = models.IntegerField(default=1, verbose_name='Priorität', help_text='Höhere Priorität = bevorzugte Platzierung')
    start_date = models.DateTimeField(blank=True, null=True, verbose_name='Startdatum')
    end_date = models.DateTimeField(blank=True, null=True, verbose_name='Enddatum')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    
    class Meta:
        verbose_name = 'Anzeigenplatzierung'
        verbose_name_plural = 'Anzeigenplatzierungen'
        ordering = ['-priority', 'zone']
        unique_together = ('advertisement', 'zone')
    
    def __str__(self):
        return f"{self.advertisement.name} in {self.zone.name}"


class AdSchedule(models.Model):
    """Zeitplan für Anzeigenschaltung"""
    WEEKDAY_CHOICES = [
        (0, 'Montag'),
        (1, 'Dienstag'),
        (2, 'Mittwoch'),
        (3, 'Donnerstag'),
        (4, 'Freitag'),
        (5, 'Samstag'),
        (6, 'Sonntag'),
    ]
    
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name='Wochentag')
    start_time = models.TimeField(verbose_name='Startzeit')
    end_time = models.TimeField(verbose_name='Endzeit')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    
    class Meta:
        verbose_name = 'Zeitplan'
        verbose_name_plural = 'Zeitpläne'
        ordering = ['weekday', 'start_time']
        unique_together = ('advertisement', 'weekday', 'start_time', 'end_time')
    
    def __str__(self):
        return f"{self.advertisement.name} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class AdTargeting(models.Model):
    """Targeting-Optionen für Anzeigen"""
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='targeting')
    
    # Device targeting
    target_desktop = models.BooleanField(default=True, verbose_name='Desktop')
    target_mobile = models.BooleanField(default=True, verbose_name='Mobile')
    target_tablet = models.BooleanField(default=True, verbose_name='Tablet')
    
    # User targeting
    target_logged_in = models.BooleanField(default=True, verbose_name='Eingeloggte Nutzer')
    target_anonymous = models.BooleanField(default=True, verbose_name='Anonyme Nutzer')
    
    # App targeting
    target_apps = models.JSONField(
        default=list, blank=True,
        verbose_name='Ziel-Apps',
        help_text='Liste der Apps, in denen die Anzeige erscheinen soll (leer = alle)'
    )
    exclude_apps = models.JSONField(
        default=list, blank=True,
        verbose_name='Ausgeschlossene Apps',
        help_text='Liste der Apps, in denen die Anzeige NICHT erscheinen soll'
    )
    
    # URL targeting
    target_urls = models.TextField(
        blank=True,
        verbose_name='Ziel-URLs',
        help_text='URLs oder URL-Muster (eine pro Zeile)'
    )
    exclude_urls = models.TextField(
        blank=True,
        verbose_name='Ausgeschlossene URLs',
        help_text='URLs oder URL-Muster (eine pro Zeile)'
    )
    
    class Meta:
        verbose_name = 'Targeting'
        verbose_name_plural = 'Targetings'
    
    def __str__(self):
        return f"Targeting für {self.advertisement.name}"


class AdImpression(models.Model):
    """Aufzeichnung von Anzeigenimpressionen"""
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='impressions')
    zone = models.ForeignKey(AdZone, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    page_url = models.URLField(verbose_name='Seiten-URL')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Impression'
        verbose_name_plural = 'Impressions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['advertisement', 'timestamp']),
            models.Index(fields=['zone', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Impression: {self.advertisement.name} - {self.timestamp}"


class AdClick(models.Model):
    """Aufzeichnung von Anzeigenklicks"""
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='clicks')
    zone = models.ForeignKey(AdZone, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    referrer_url = models.URLField(blank=True, verbose_name='Referrer URL')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Klick'
        verbose_name_plural = 'Klicks'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['advertisement', 'timestamp']),
            models.Index(fields=['zone', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Klick: {self.advertisement.name} - {self.timestamp}"
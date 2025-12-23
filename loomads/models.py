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
    enable_video_preroll_zones = models.JSONField(default=dict, verbose_name='Video Pre-Roll-Zonen pro App')
    enable_video_overlay_zones = models.JSONField(default=dict, verbose_name='Video Overlay-Zonen pro App')
    enable_video_popup_zones = models.JSONField(default=dict, verbose_name='Video Pop-up-Zonen pro App')
    enable_content_card_zones = models.JSONField(default=dict, verbose_name='Content Card-Zonen pro App')
    enable_notification_zones = models.JSONField(default=dict, verbose_name='Benachrichtigungs-Zonen pro App')
    
    # Global zone controls
    global_header_enabled = models.BooleanField(default=True, verbose_name='Header-Zonen global')
    global_footer_enabled = models.BooleanField(default=True, verbose_name='Footer-Zonen global')
    global_sidebar_enabled = models.BooleanField(default=True, verbose_name='Sidebar-Zonen global')
    global_infeed_enabled = models.BooleanField(default=True, verbose_name='In-Feed-Zonen global')
    global_modal_enabled = models.BooleanField(default=True, verbose_name='Modal-Zonen global')
    global_video_preroll_enabled = models.BooleanField(default=True, verbose_name='Video Pre-Roll-Zonen global')
    global_video_overlay_enabled = models.BooleanField(default=True, verbose_name='Video Overlay-Zonen global')
    global_video_popup_enabled = models.BooleanField(default=True, verbose_name='Video Pop-up-Zonen global')
    global_content_card_enabled = models.BooleanField(default=True, verbose_name='Content Card-Zonen global')
    global_notification_enabled = models.BooleanField(default=True, verbose_name='Benachrichtigungs-Zonen global')
    
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
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Startdatum',
        help_text='Leer lassen für "Ab sofort"'
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enddatum',
        help_text='Leer lassen für "Unbegrenzt"'
    )
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
    daily_click_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tägliches Klick-Limit',
        help_text='Maximale Anzahl der Klicks pro Tag (leer = unbegrenzt)'
    )
    total_click_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Gesamt Klick-Limit',
        help_text='Maximale Anzahl der Klicks insgesamt (leer = unbegrenzt)'
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


class AppCampaign(models.Model):
    """App-spezifische Werbekampagne - automatische Zuordnung zu allen App-Zonen"""

    APP_CHOICES = [
        ('loomline', 'LoomLine'),
        ('loomconnect', 'LoomConnect'),
        ('keyengine', 'KeyEngine'),
        ('fileshare', 'FileShara'),
        ('streamrec', 'StreamRec'),
        ('promptpro', 'PromptPro'),
        ('blog', 'Blog'),
        ('videos', 'Video-Management'),
        ('chat', 'Chat-System'),
        ('todos', 'Todos'),
        ('core', 'Dashboard/Startseite'),
        ('image_editor', 'Image Editor'),
        ('amortization_calculator', 'Amortisationsrechner'),
        ('pdf_sucher', 'PDF Sucher'),
        ('naturmacher', 'Naturmacher'),
        ('lighting_tools', 'Lighting Tools'),
        ('shopify_manager', 'Shopify Manager'),
        ('global', 'Global Bereiche'),
        ('dashboard', 'Dashboard (Legacy)'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('active', 'Aktiv'),
        ('paused', 'Pausiert'),
        ('completed', 'Abgeschlossen'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Sehr niedrig'),
        (2, 'Niedrig'),
        (3, 'Normal'),
        (4, 'Hoch'),
        (5, 'Sehr hoch'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='App-Kampagnenname')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    app_target = models.CharField(
        max_length=30,
        choices=APP_CHOICES,
        verbose_name='Ziel-App',
        help_text='App für die diese Kampagne geschaltet wird'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='app_campaigns')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        verbose_name='Priorität',
        help_text='Höhere Priorität = häufigere Anzeige in App-Zonen'
    )

    # Zeitplanung
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Startdatum',
        help_text='Leer lassen für "Ab sofort"'
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enddatum',
        help_text='Leer lassen für "Unbegrenzt"'
    )

    # Automatische Zone-Zuordnung Optionen
    auto_include_new_zones = models.BooleanField(
        default=True,
        verbose_name='Neue Zonen automatisch einbeziehen',
        help_text='Neue Zonen der App automatisch zu dieser Kampagne hinzufügen'
    )
    exclude_zone_types = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name='Ausgeschlossene Zone-Typen',
        help_text='Zone-Typen die von dieser App-Kampagne ausgeschlossen werden sollen'
    )

    # Limits
    daily_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tägliches Impression-Limit (pro App)',
        help_text='Maximale Anzahl der Impressions pro Tag für alle App-Zonen (leer = unbegrenzt)'
    )
    total_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Gesamt Impression-Limit (pro App)',
        help_text='Maximale Anzahl der Impressions insgesamt für alle App-Zonen (leer = unbegrenzt)'
    )
    daily_click_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tägliches Klick-Limit (pro App)',
        help_text='Maximale Anzahl der Klicks pro Tag für alle App-Zonen (leer = unbegrenzt)'
    )
    total_click_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Gesamt Klick-Limit (pro App)',
        help_text='Maximale Anzahl der Klicks insgesamt für alle App-Zonen (leer = unbegrenzt)'
    )

    # Gewichtung und Performance
    weight_multiplier = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(5.0)],
        verbose_name='Gewichtungs-Multiplikator',
        help_text='Multiplikator für die Anzeigengewichtung in App-Zonen (0.1 - 5.0)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'App-Kampagne'
        verbose_name_plural = 'App-Kampagnen'
        ordering = ['-priority', '-created_at']
        unique_together = ['name', 'app_target']  # Ein Kampagnenname pro App

    def __str__(self):
        return f"{self.name} ({self.get_app_target_display()})"

    @property
    def is_active(self):
        """Check if campaign is currently active"""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )

    def get_target_zones(self):
        """Get all zones that belong to this app campaign's target"""
        from .views_frontend import determine_app_from_zone_code

        all_zones = AdZone.objects.filter(is_active=True)
        target_zones = []

        for zone in all_zones:
            zone_app = determine_app_from_zone_code(zone.code)
            if zone_app == self.app_target:
                # Check if zone type is excluded
                if zone.zone_type not in self.exclude_zone_types:
                    target_zones.append(zone)

        return target_zones

    def get_target_zones_count(self):
        """Get count of target zones"""
        return len(self.get_target_zones())

    def get_total_impressions(self):
        """Get total impressions for all ads in this app campaign"""
        return sum(ad.impressions_count for ad in self.app_advertisements.all())

    def get_total_clicks(self):
        """Get total clicks for all ads in this app campaign"""
        return sum(ad.clicks_count for ad in self.app_advertisements.all())

    def get_ctr(self):
        """Get Click-Through Rate for this app campaign"""
        impressions = self.get_total_impressions()
        clicks = self.get_total_clicks()
        if impressions > 0:
            return (clicks / impressions) * 100
        return 0

    def sync_zones(self):
        """Synchronize campaign with current app zones (add new zones if auto_include_new_zones is True)"""
        if not self.auto_include_new_zones:
            return

        target_zones = self.get_target_zones()

        # Add campaign to advertisements that target these zones
        for ad in self.app_advertisements.all():
            current_zones = set(ad.zones.all())
            target_zones_set = set(target_zones)

            # Add new zones to the advertisement
            new_zones = target_zones_set - current_zones
            if new_zones:
                ad.zones.add(*new_zones)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-sync zones after saving if auto_include_new_zones is enabled
        if self.auto_include_new_zones:
            self.sync_zones()


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


class AppAdvertisement(models.Model):
    """App-spezifische Werbeanzeige - automatisch allen App-Zonen zugeordnet"""

    AD_TYPES = [
        ('banner', 'Banner'),
        ('text', 'Text-Anzeige'),
        ('image', 'Bild-Anzeige'),
        ('video', 'Video-Anzeige'),
        ('html', 'HTML/Rich Content'),
        ('native', 'Native Content'),
    ]

    DEVICE_TYPES = [
        ('all', 'Alle Geräte'),
        ('desktop', 'Desktop'),
        ('mobile', 'Mobil'),
        ('tablet', 'Tablet'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_campaign = models.ForeignKey(
        AppCampaign,
        on_delete=models.CASCADE,
        related_name='app_advertisements'
    )
    name = models.CharField(max_length=200, verbose_name='Anzeigenname')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    ad_type = models.CharField(max_length=20, choices=AD_TYPES, default='html')

    # Content
    title = models.CharField(max_length=200, blank=True, verbose_name='Titel')
    description_text = models.TextField(blank=True, verbose_name='Beschreibungstext')
    html_content = models.TextField(blank=True, verbose_name='HTML-Inhalt')
    image = models.ImageField(upload_to='loomads/images/', blank=True, null=True)
    video_url = models.URLField(blank=True, verbose_name='Video-URL')
    link_url = models.URLField(verbose_name='Ziel-URL')
    link_text = models.CharField(max_length=100, blank=True, verbose_name='Link-Text')

    # Automatische Zone-Zuordnung
    zones = models.ManyToManyField(
        AdZone,
        blank=True,
        related_name='app_advertisements',
        help_text='Wird automatisch mit allen App-Zonen synchronisiert'
    )

    # Settings
    weight = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Gewichtung',
        help_text='Anzeigengewichtung (1-10) - wird mit App-Kampagne Multiplikator kombiniert'
    )
    device_targeting = models.CharField(
        max_length=20,
        choices=DEVICE_TYPES,
        default='all',
        verbose_name='Geräte-Targeting'
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    # Performance tracking
    impressions_count = models.PositiveIntegerField(default=0)
    clicks_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'App-Anzeige'
        verbose_name_plural = 'App-Anzeigen'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.app_campaign.name})"

    @property
    def effective_weight(self):
        """Calculate effective weight including app campaign multiplier"""
        return self.weight * self.app_campaign.weight_multiplier

    @property
    def ctr(self):
        """Click-Through-Rate berechnen"""
        if self.impressions_count > 0:
            return (self.clicks_count / self.impressions_count) * 100
        return 0

    def get_ctr(self):
        """Get Click-Through Rate for templates"""
        return self.ctr

    def sync_with_app_zones(self):
        """Synchronize this advertisement with all zones of the target app"""
        target_zones = self.app_campaign.get_target_zones()

        # Clear current zones and add all app zones
        self.zones.clear()
        self.zones.add(*target_zones)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-sync with app zones after saving
        if self.app_campaign.auto_include_new_zones:
            self.sync_with_app_zones()


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
    
    # Browser targeting
    target_browsers = models.JSONField(
        default=list, blank=True,
        verbose_name='Browser',
        help_text='Liste der Browser (chrome, firefox, safari, edge, opera, andere)'
    )
    exclude_browsers = models.JSONField(
        default=list, blank=True,
        verbose_name='Ausgeschlossene Browser',
        help_text='Browser die ausgeschlossen werden sollen'
    )
    
    # Operating System targeting
    target_os = models.JSONField(
        default=list, blank=True,
        verbose_name='Betriebssysteme',
        help_text='Liste der Betriebssysteme (windows, macos, linux, ios, android, andere)'
    )
    exclude_os = models.JSONField(
        default=list, blank=True,
        verbose_name='Ausgeschlossene Betriebssysteme',
        help_text='Betriebssysteme die ausgeschlossen werden sollen'
    )
    
    # Referrer targeting
    target_referrers = models.TextField(
        blank=True,
        verbose_name='Referrer-Muster',
        help_text='Referrer-URLs oder Muster (eine pro Zeile), z.B. google.com, facebook.com, direkt'
    )
    exclude_referrers = models.TextField(
        blank=True,
        verbose_name='Ausgeschlossene Referrer',
        help_text='Referrer die ausgeschlossen werden sollen'
    )
    
    # Geographic targeting
    target_cities = models.JSONField(
        default=list, blank=True,
        verbose_name='Städte/Regionen',
        help_text='Liste der Städte oder Regionen'
    )
    exclude_cities = models.JSONField(
        default=list, blank=True,
        verbose_name='Ausgeschlossene Städte/Regionen',
        help_text='Städte oder Regionen die ausgeschlossen werden sollen'
    )
    
    # Time-based targeting
    target_weekdays = models.JSONField(
        default=list, blank=True,
        verbose_name='Wochentage',
        help_text='Liste der Wochentage (0=Montag, 6=Sonntag)'
    )
    target_hours_start = models.TimeField(
        null=True, blank=True,
        verbose_name='Startzeit',
        help_text='Ab welcher Uhrzeit soll die Anzeige erscheinen'
    )
    target_hours_end = models.TimeField(
        null=True, blank=True,
        verbose_name='Endzeit',
        help_text='Bis welcher Uhrzeit soll die Anzeige erscheinen'
    )
    target_date_start = models.DateField(
        null=True, blank=True,
        verbose_name='Startdatum',
        help_text='Ab welchem Datum soll die Anzeige erscheinen'
    )
    target_date_end = models.DateField(
        null=True, blank=True,
        verbose_name='Enddatum',
        help_text='Bis welchem Datum soll die Anzeige erscheinen'
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


class ZoneIntegration(models.Model):
    """Verwaltet Zone-Integrationen in verschiedenen Templates"""
    VISIBILITY_CHOICES = [
        ('all', 'Alle Benutzer'),
        ('authenticated', 'Eingeloggte User'),
        ('anonymous', 'Anonyme Besucher'),
        ('superuser', 'Nur Superuser'),
        ('premium', 'Premium-Benutzer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('inactive', 'Inaktiv'),
        ('planned', 'Geplant'),
        ('deprecated', 'Veraltet'),
    ]
    
    zone_code = models.CharField(max_length=100, verbose_name='Zone Code')
    template_path = models.CharField(max_length=200, verbose_name='Template-Pfad')
    visibility = models.CharField(
        max_length=20, 
        choices=VISIBILITY_CHOICES, 
        default='all',
        verbose_name='Sichtbar für'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        verbose_name='Status'
    )
    description = models.TextField(
        blank=True, 
        verbose_name='Beschreibung',
        help_text='Zusätzliche Informationen zur Integration'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Zone Integration'
        verbose_name_plural = 'Zone Integrationen'
        unique_together = ['zone_code', 'template_path']
        ordering = ['template_path', 'zone_code']
    
    def __str__(self):
        return f"{self.zone_code} in {self.template_path}"
    
    def get_status_badge_class(self):
        """Returns Bootstrap badge class for status"""
        status_classes = {
            'active': 'bg-success',
            'inactive': 'bg-secondary', 
            'planned': 'bg-warning',
            'deprecated': 'bg-danger',
        }
        return status_classes.get(self.status, 'bg-secondary')


class AutoCampaignFormat(models.Model):
    """Automatische Kampagnenformat-Definitionen für gleiche Zonen-Typen und -Größen"""
    
    FORMAT_TYPES = [
        ('banner_728x90', 'Banner 728x90 (Header/Footer)'),
        ('sidebar_300x250', 'Sidebar 300x250'),
        ('content_card_350x200', 'Content Card 350x200'),
        ('content_card_350x250', 'Content Card 350x250'), 
        ('video_overlay_300x100', 'Video Overlay 300x100'),
        ('video_preroll_640x360', 'Video Pre-Roll 640x360'),
        ('modal_400x300', 'Modal 400x300'),
        ('notification_300x80', 'Benachrichtigung 300x80'),
        ('custom', 'Benutzerdefiniert'),
    ]
    
    GROUPING_STRATEGIES = [
        ('by_type', 'Nach Zone-Typ gruppieren'),
        ('by_dimensions', 'Nach Dimensionen gruppieren'),
        ('by_type_and_dimensions', 'Nach Typ UND Dimensionen gruppieren'),
        ('by_app', 'Nach App gruppieren'),
        ('mixed', 'Gemischte Strategie'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='Format-Name')
    format_type = models.CharField(max_length=50, choices=FORMAT_TYPES, default='custom')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    
    # Format-Spezifikationen
    target_zone_types = models.JSONField(
        default=list,
        verbose_name='Ziel-Zone-Typen', 
        help_text='Liste der Zone-Typen, z.B. ["header", "footer"]'
    )
    target_dimensions = models.JSONField(
        default=list,
        verbose_name='Ziel-Dimensionen',
        help_text='Liste der Dimensionen, z.B. ["728x90", "320x50"]'
    )
    excluded_zones = models.JSONField(
        default=list,
        verbose_name='Ausgeschlossene Zonen',
        help_text='Zone-Codes die ausgeschlossen werden sollen'
    )
    
    # Automatische Gruppierung
    grouping_strategy = models.CharField(
        max_length=30,
        choices=GROUPING_STRATEGIES,
        default='by_type_and_dimensions'
    )
    auto_assign_similar_zones = models.BooleanField(
        default=True,
        verbose_name='Ähnliche Zonen automatisch zuweisen'
    )
    
    # Einstellungen
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    priority = models.IntegerField(
        default=1,
        verbose_name='Priorität',
        help_text='Höhere Priorität = bevorzugte Verwendung'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Auto-Kampagnenformat'
        verbose_name_plural = 'Auto-Kampagnenformate'
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.format_type})"
    
    def get_matching_zones(self):
        """Ermittelt alle Zonen, die diesem Format entsprechen"""
        from django.db.models import Q
        
        zones = AdZone.objects.filter(is_active=True)
        
        # Nach Zone-Typen filtern
        if self.target_zone_types:
            zones = zones.filter(zone_type__in=self.target_zone_types)
        
        # Nach Dimensionen filtern  
        if self.target_dimensions:
            dimension_q = Q()
            for dim in self.target_dimensions:
                if 'x' in dim:
                    width, height = dim.split('x')
                    dimension_q |= Q(width=int(width), height=int(height))
            if dimension_q:
                zones = zones.filter(dimension_q)
        
        # Ausgeschlossene Zonen entfernen
        if self.excluded_zones:
            zones = zones.exclude(code__in=self.excluded_zones)
        
        return zones
    
    def get_zone_count(self):
        """Anzahl der passenden Zonen"""
        return self.get_matching_zones().count()
    
    def create_format_key(self):
        """Erstellt einen eindeutigen Format-Key"""
        if self.target_zone_types and self.target_dimensions:
            types = "_".join(sorted(self.target_zone_types))
            dims = "_".join(sorted(self.target_dimensions))
            return f"{types}_{dims}"
        return f"custom_{self.id}"


class AutoCampaign(models.Model):
    """Automatische Kampagnen die gleiche Formate intelligent zusammenfassen"""
    
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('active', 'Aktiv'),
        ('paused', 'Pausiert'),
        ('completed', 'Abgeschlossen'),
        ('auto_paused', 'Automatisch pausiert'),
    ]
    
    CONTENT_STRATEGIES = [
        ('single_creative', 'Ein Kreativ für alle Zonen'),
        ('format_optimized', 'Pro Format optimiert'),
        ('zone_specific', 'Zonenspezifisch angepasst'),
        ('a_b_testing', 'A/B Testing'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='Kampagnen-Name')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    
    # Format-Zuordnung
    target_format = models.ForeignKey(
        AutoCampaignFormat,
        on_delete=models.CASCADE,
        related_name='campaigns',
        verbose_name='Ziel-Format'
    )
    
    # Automatische Einstellungen
    content_strategy = models.CharField(
        max_length=30,
        choices=CONTENT_STRATEGIES,
        default='format_optimized'
    )
    auto_optimize_performance = models.BooleanField(
        default=True,
        verbose_name='Performance automatisch optimieren'
    )
    auto_pause_low_performers = models.BooleanField(
        default=False,
        verbose_name='Schwache Performer automatisch pausieren'
    )
    performance_threshold_ctr = models.FloatField(
        default=0.5,
        verbose_name='CTR-Schwellenwert (%)',
        help_text='Unter diesem CTR werden Ads automatisch pausiert'
    )
    
    # Standard Kampagnen-Felder
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auto_campaigns')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Startdatum',
        help_text='Leer lassen für "Ab sofort"'
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enddatum',
        help_text='Leer lassen für "Unbegrenzt"'
    )
    
    # Budget & Limits
    daily_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tägliches Impression-Limit pro Zone'
    )
    total_impression_limit = models.IntegerField(
        null=True, blank=True,
        verbose_name='Gesamt Impression-Limit'
    )
    
    # Automatische Verwaltung
    last_optimization_run = models.DateTimeField(null=True, blank=True)
    auto_created_ads_count = models.IntegerField(default=0)
    performance_score = models.FloatField(
        default=0.0,
        verbose_name='Performance-Score',
        help_text='Automatisch berechneter Performance-Score (0-100)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Automatische Kampagne'
        verbose_name_plural = 'Automatische Kampagnen'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} (Auto: {self.target_format.name})"
    
    @property
    def is_active(self):
        """Prüft ob die Kampagne aktiv ist"""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )
    
    def get_target_zones(self):
        """Ermittelt alle Ziel-Zonen basierend auf dem Format"""
        return self.target_format.get_matching_zones()
    
    def get_auto_ads(self):
        """Alle automatisch erstellten Ads für diese Kampagne"""
        return self.auto_advertisements.filter(is_active=True)
    
    def calculate_performance_score(self):
        """Berechnet den Performance-Score basierend auf den Ads"""
        ads = self.get_auto_ads()
        if not ads.exists():
            return 0.0
        
        total_impressions = sum(ad.impressions_count for ad in ads)
        total_clicks = sum(ad.clicks_count for ad in ads)
        
        if total_impressions == 0:
            return 0.0
        
        # CTR-basierter Score
        ctr = (total_clicks / total_impressions) * 100
        
        # Zone-Abdeckung Score
        target_zones_count = self.get_target_zones().count()
        covered_zones_count = ads.values('zones').distinct().count()
        coverage_score = (covered_zones_count / max(target_zones_count, 1)) * 100
        
        # Gewichteter Gesamtscore
        performance_score = (ctr * 0.7) + (coverage_score * 0.3)
        return min(performance_score, 100.0)
    
    def update_performance_score(self):
        """Aktualisiert den Performance-Score"""
        self.performance_score = self.calculate_performance_score()
        self.save(update_fields=['performance_score'])
        return self.performance_score
    
    def auto_create_ads_for_format(self, base_creative):
        """Erstellt automatisch Ads für alle passenden Zonen des Formats"""
        target_zones = self.get_target_zones()
        created_ads = []
        
        for zone in target_zones:
            # Prüfe ob bereits eine Ad für diese Zone existiert
            existing_ad = self.auto_advertisements.filter(zones=zone).first()
            if existing_ad:
                continue
            
            # Erstelle neue Auto-Advertisement
            auto_ad = AutoAdvertisement.objects.create(
                auto_campaign=self,
                base_creative=base_creative,
                target_zone=zone,
                name=f"{self.name} - {zone.code}",
                is_active=True
            )
            created_ads.append(auto_ad)
        
        self.auto_created_ads_count = self.auto_advertisements.count()
        self.save(update_fields=['auto_created_ads_count'])
        return created_ads
    
    def optimize_performance(self):
        """Führt automatische Performance-Optimierung durch"""
        if not self.auto_optimize_performance:
            return
        
        results = {
            'paused_ads': [],
            'optimized_ads': [],
            'total_score': 0
        }
        
        # Performance-Score aktualisieren
        results['total_score'] = self.update_performance_score()
        
        # Schwache Performer pausieren
        if self.auto_pause_low_performers:
            threshold_ctr = self.performance_threshold_ctr
            auto_ads = self.get_auto_ads()
            
            for auto_ad in auto_ads:
                if auto_ad.advertisement and auto_ad.advertisement.ctr < threshold_ctr:
                    auto_ad.advertisement.is_active = False
                    auto_ad.advertisement.save()
                    results['paused_ads'].append(auto_ad.advertisement.name)
        
        self.last_optimization_run = timezone.now()
        self.save(update_fields=['last_optimization_run'])
        return results


class AutoAdvertisement(models.Model):
    """Automatisch generierte Advertisements für Auto-Kampagnen"""
    
    GENERATION_STRATEGIES = [
        ('direct_copy', 'Direkte Kopie'),
        ('dimension_adapted', 'An Dimensionen angepasst'),
        ('format_optimized', 'Format-optimiert'),
        ('ai_generated', 'KI-generiert'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auto_campaign = models.ForeignKey(
        AutoCampaign,
        on_delete=models.CASCADE,
        related_name='auto_advertisements'
    )
    
    # Referenz-Creative
    base_creative = models.TextField(
        verbose_name='Basis-Creative',
        help_text='JSON mit Creative-Daten (Bild-URL, Text, etc.)'
    )
    
    # Automatisch generierte Advertisement
    advertisement = models.OneToOneField(
        Advertisement,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='auto_generated_from'
    )
    
    # Ziel-Zone
    target_zone = models.ForeignKey(
        AdZone,
        on_delete=models.CASCADE,
        verbose_name='Ziel-Zone'
    )
    
    # Generation-Details
    generation_strategy = models.CharField(
        max_length=30,
        choices=GENERATION_STRATEGIES,
        default='format_optimized'
    )
    generation_metadata = models.JSONField(
        default=dict,
        verbose_name='Generierungs-Metadaten'
    )
    
    # Status
    name = models.CharField(max_length=200, verbose_name='Name')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    performance_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Automatische Anzeige'
        verbose_name_plural = 'Automatische Anzeigen'
        ordering = ['-created_at']
        unique_together = ('auto_campaign', 'target_zone')
    
    def __str__(self):
        return f"{self.name} → {self.target_zone.code}"
    
    def generate_advertisement(self):
        """Generiert die tatsächliche Advertisement basierend auf dem Base-Creative"""
        import json
        
        try:
            creative_data = json.loads(self.base_creative) if isinstance(self.base_creative, str) else self.base_creative
        except (json.JSONDecodeError, TypeError):
            creative_data = {}
        
        # Advertisement erstellen oder aktualisieren
        if not self.advertisement:
            self.advertisement = Advertisement.objects.create(
                campaign_id=None,  # Wird durch Auto-Campaign verwaltet
                name=self.name,
                ad_type=creative_data.get('type', 'image'),
                title=creative_data.get('title', ''),
                description=creative_data.get('description', ''),
                target_url=creative_data.get('target_url', '#'),
                target_type=creative_data.get('target_type', '_blank'),
                weight=creative_data.get('weight', 5),
                is_active=self.is_active
            )
            
            # Zone zuweisen
            self.advertisement.zones.add(self.target_zone)
            
            # Format-spezifische Anpassungen
            self.apply_format_optimizations(creative_data)
            
            self.save()
        
        return self.advertisement
    
    def apply_format_optimizations(self, creative_data):
        """Wendet format-spezifische Optimierungen an"""
        if not self.advertisement:
            return
        
        zone = self.target_zone
        ad = self.advertisement
        
        # Dimensionsbasierte Anpassungen
        if zone.width == 728 and zone.height == 90:
            # Banner-Format
            self.generation_metadata['optimized_for'] = 'banner_728x90'
        elif zone.width == 300 and zone.height == 250:
            # Sidebar-Format
            self.generation_metadata['optimized_for'] = 'sidebar_300x250'
        
        # Zone-Typ basierte Anpassungen
        if zone.zone_type in ['header', 'footer']:
            # Weniger aggressiver Text für Header/Footer
            self.generation_metadata['tone'] = 'subtle'
        elif zone.zone_type == 'video_overlay':
            # Transparenter Hintergrund für Video-Overlays
            self.generation_metadata['background'] = 'transparent'
        
        self.save(update_fields=['generation_metadata'])
    
    def calculate_performance_score(self):
        """Berechnet Performance-Score für diese Auto-Ad"""
        if not self.advertisement:
            return 0.0
        
        ad = self.advertisement
        if ad.impressions_count == 0:
            return 0.0
        
        # CTR als Hauptmetrik
        ctr = (ad.clicks_count / ad.impressions_count) * 100
        
        # Zone-spezifische Gewichtung
        zone_multiplier = 1.0
        if self.target_zone.zone_type == 'header':
            zone_multiplier = 1.2  # Header-Ads sind wertvoller
        elif self.target_zone.zone_type == 'footer':
            zone_multiplier = 0.8  # Footer-Ads weniger wertvoll
        
        score = ctr * zone_multiplier
        return min(score, 100.0)

    def update_performance_score(self):
        """Aktualisiert den Performance-Score"""
        self.performance_score = self.calculate_performance_score()
        self.save(update_fields=['performance_score'])
        return self.performance_score


class AdWizardDraft(models.Model):
    """Speichert Entwürfe während des Schritt-für-Schritt Ad-Erstellungs-Assistenten"""

    WIZARD_STEPS = [
        ('app_selection', 'App-Auswahl'),
        ('campaign_details', 'Kampagnen-Details'),
        ('format_selection', 'Format-Auswahl'),
        ('creative_upload', 'Creative-Upload'),
        ('review', 'Überprüfung'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ad_wizard_drafts',
        verbose_name='Benutzer'
    )

    # Wizard State
    current_step = models.CharField(
        max_length=30,
        choices=WIZARD_STEPS,
        default='app_selection',
        verbose_name='Aktueller Schritt'
    )
    completed_steps = models.JSONField(
        default=list,
        verbose_name='Abgeschlossene Schritte',
        help_text='Liste der bereits abgeschlossenen Schritte'
    )

    # Wizard Data (JSON für Flexibilität)
    wizard_data = models.JSONField(
        default=dict,
        verbose_name='Wizard-Daten',
        help_text='Alle gesammelten Daten aus den Wizard-Schritten'
    )

    # Campaign Draft Data
    selected_app = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Ausgewählte App'
    )
    campaign_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Kampagnenname'
    )
    campaign_description = models.TextField(
        blank=True,
        verbose_name='Kampagnen-Beschreibung'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        verbose_name='Verfällt am',
        help_text='Entwurf wird nach diesem Datum automatisch gelöscht'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv',
        help_text='Inaktive Entwürfe werden nicht mehr angezeigt'
    )

    class Meta:
        verbose_name = 'Ad-Wizard Entwurf'
        verbose_name_plural = 'Ad-Wizard Entwürfe'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Entwurf von {self.user.username} - {self.get_current_step_display()}"

    def is_expired(self):
        """Prüft ob der Entwurf abgelaufen ist"""
        return timezone.now() > self.expires_at

    def mark_step_completed(self, step):
        """Markiert einen Schritt als abgeschlossen"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            self.save(update_fields=['completed_steps', 'updated_at'])

    def get_next_step(self):
        """Gibt den nächsten Schritt zurück"""
        steps = [choice[0] for choice in self.WIZARD_STEPS]
        try:
            current_index = steps.index(self.current_step)
            if current_index < len(steps) - 1:
                return steps[current_index + 1]
        except ValueError:
            pass
        return None

    def advance_to_next_step(self):
        """Geht zum nächsten Schritt"""
        next_step = self.get_next_step()
        if next_step:
            self.mark_step_completed(self.current_step)
            self.current_step = next_step
            self.save(update_fields=['current_step', 'updated_at'])
            return True
        return False

    def get_progress_percentage(self):
        """Berechnet den Fortschritt in Prozent"""
        total_steps = len(self.WIZARD_STEPS)
        completed = len(self.completed_steps)
        return int((completed / total_steps) * 100)

    def update_wizard_data(self, step_data):
        """Aktualisiert die Wizard-Daten für den aktuellen Schritt"""
        self.wizard_data[self.current_step] = step_data
        self.save(update_fields=['wizard_data', 'updated_at'])

    def get_step_data(self, step):
        """Holt Daten für einen bestimmten Schritt"""
        return self.wizard_data.get(step, {})

    @classmethod
    def cleanup_expired_drafts(cls):
        """Löscht alle abgelaufenen Entwürfe"""
        now = timezone.now()
        expired = cls.objects.filter(expires_at__lte=now)
        count = expired.count()
        expired.delete()
        return count


# =============================================================================
# SIMPLE ADS - Vereinfachtes, globales Anzeigen-System
# =============================================================================

class SimpleAd(models.Model):
    """
    Einfache, globale Anzeige die sich automatisch an alle Zonen anpasst.
    Keine Kampagnen, kein komplexes Targeting - nur eine Anzeige erstellen und fertig.
    """

    TEMPLATE_STYLES = [
        ('minimal', 'Minimal - Nur Text'),
        ('card', 'Card - Mit Rahmen und Schatten'),
        ('gradient', 'Gradient - Farbverlauf-Hintergrund'),
        ('banner', 'Banner - Breites Format'),
        ('highlight', 'Highlight - Auffällig mit Akzentfarbe'),
        ('dark', 'Dark - Dunkler Hintergrund'),
        ('glass', 'Glass - Glasmorphismus-Effekt'),
        ('neon', 'Neon - Leuchtende Rahmen'),
        ('retro', 'Retro - Vintage-Look'),
        ('threed', '3D - Mit Tiefeneffekt'),
    ]

    COLOR_SCHEMES = [
        ('blue', 'Blau'),
        ('green', 'Grün'),
        ('purple', 'Lila'),
        ('orange', 'Orange'),
        ('red', 'Rot'),
        ('teal', 'Türkis'),
        ('pink', 'Pink'),
        ('gray', 'Grau'),
        ('custom', 'Eigene Farbe'),
    ]

    ANIMATION_CHOICES = [
        ('none', 'Keine Animation'),
        ('fade', 'Fade-In'),
        ('slide', 'Slide-In'),
        ('pulse', 'Pulse beim Hover'),
        ('bounce', 'Bounce'),
        ('shake', 'Shake beim Hover'),
    ]

    BADGE_CHOICES = [
        ('', 'Kein Badge'),
        ('neu', 'NEU'),
        ('sale', 'SALE'),
        ('hot', 'HOT'),
        ('top', 'TOP'),
        ('tipp', 'TIPP'),
        ('limited', 'LIMITIERT'),
        ('custom', 'Eigener Text'),
    ]

    TARGET_AUDIENCE_CHOICES = [
        ('all', 'Alle Nutzer'),
        ('logged_in', 'Nur eingeloggte Nutzer'),
        ('anonymous', 'Nur anonyme Besucher'),
    ]

    # Bootstrap Icons für Icon-Auswahl
    ICON_CHOICES = [
        ('', 'Kein Icon'),
        ('bi-star-fill', 'Stern'),
        ('bi-heart-fill', 'Herz'),
        ('bi-lightning-fill', 'Blitz'),
        ('bi-fire', 'Feuer'),
        ('bi-gift', 'Geschenk'),
        ('bi-trophy', 'Pokal'),
        ('bi-rocket', 'Rakete'),
        ('bi-megaphone', 'Megaphone'),
        ('bi-percent', 'Prozent'),
        ('bi-tag-fill', 'Tag'),
        ('bi-cart-fill', 'Warenkorb'),
        ('bi-cash-coin', 'Geld'),
        ('bi-bell-fill', 'Glocke'),
        ('bi-chat-heart-fill', 'Chat-Herz'),
        ('bi-emoji-smile', 'Smiley'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Content
    title = models.CharField(
        max_length=100,
        verbose_name='Titel',
        help_text='Kurzer, aussagekräftiger Titel (max. 100 Zeichen)'
    )
    description = models.TextField(
        max_length=300,
        blank=True,
        verbose_name='Beschreibung',
        help_text='Optionale Beschreibung (max. 300 Zeichen)'
    )
    image = models.ImageField(
        upload_to='loomads/simple/',
        blank=True,
        null=True,
        verbose_name='Bild',
        help_text='Optionales Bild (wird automatisch skaliert)'
    )
    button_text = models.CharField(
        max_length=30,
        default='Mehr erfahren',
        verbose_name='Button-Text',
        help_text='Text auf dem Aktions-Button (max. 30 Zeichen)'
    )
    target_url = models.URLField(
        verbose_name='Ziel-URL',
        help_text='Wohin soll die Anzeige verlinken?'
    )
    open_in_new_tab = models.BooleanField(
        default=True,
        verbose_name='In neuem Tab öffnen'
    )

    # Styling
    template_style = models.CharField(
        max_length=20,
        choices=TEMPLATE_STYLES,
        default='card',
        verbose_name='Design-Vorlage',
        help_text='Wähle einen Stil für die Anzeige'
    )
    color_scheme = models.CharField(
        max_length=20,
        choices=COLOR_SCHEMES,
        default='blue',
        verbose_name='Farbschema'
    )
    custom_color = models.CharField(
        max_length=7,
        blank=True,
        verbose_name='Eigene Farbe',
        help_text='Hex-Farbe z.B. #FF5733 (nur bei "Eigene Farbe")'
    )

    # Display Settings
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv',
        help_text='Nur aktive Anzeigen werden angezeigt'
    )
    weight = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Gewichtung',
        help_text='1-10: Höhere Werte = häufigere Anzeige'
    )

    # Animation
    animation = models.CharField(
        max_length=20,
        choices=ANIMATION_CHOICES,
        default='none',
        verbose_name='Animation',
        help_text='Animations-Effekt für die Anzeige'
    )

    # Badge/Label
    badge = models.CharField(
        max_length=20,
        choices=BADGE_CHOICES,
        blank=True,
        default='',
        verbose_name='Badge',
        help_text='Optionales Badge/Label'
    )
    badge_custom_text = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Eigener Badge-Text',
        help_text='Nur bei "Eigener Text"'
    )

    # Icon (Alternative zu Bild)
    icon = models.CharField(
        max_length=50,
        choices=ICON_CHOICES,
        blank=True,
        default='',
        verbose_name='Icon',
        help_text='Bootstrap Icon (Alternative zu Bild)'
    )

    # Video-Hintergrund
    video_url = models.URLField(
        blank=True,
        verbose_name='Video-URL',
        help_text='URL zu einem kurzen Loop-Video (MP4)'
    )

    # Zeitplanung
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Startdatum',
        help_text='Ab wann soll die Anzeige erscheinen? (leer = sofort)'
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enddatum',
        help_text='Bis wann soll die Anzeige erscheinen? (leer = unbegrenzt)'
    )

    # Countdown
    countdown_enabled = models.BooleanField(
        default=False,
        verbose_name='Countdown anzeigen',
        help_text='Zeigt einen Countdown bis zum Enddatum'
    )
    countdown_text = models.CharField(
        max_length=50,
        blank=True,
        default='Nur noch:',
        verbose_name='Countdown-Text',
        help_text='Text vor dem Countdown'
    )

    # Zielgruppen
    target_audience = models.CharField(
        max_length=20,
        choices=TARGET_AUDIENCE_CHOICES,
        default='all',
        verbose_name='Zielgruppe',
        help_text='Für welche Nutzer soll die Anzeige sichtbar sein?'
    )

    # App-Filter
    app_filter = models.JSONField(
        default=list,
        blank=True,
        verbose_name='App-Filter',
        help_text='Nur in diesen Apps anzeigen (leer = alle)'
    )
    exclude_apps = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Apps ausschließen',
        help_text='In diesen Apps nicht anzeigen'
    )

    # A/B Testing
    variant_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Varianten-Name',
        help_text='Name für A/B-Test (z.B. "Variante A")'
    )
    ab_test_group = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='A/B-Test Gruppe',
        help_text='Anzeigen mit gleichem Gruppennamen werden getestet'
    )

    # Optional: Zone-Einschränkungen (leer = alle Zonen)
    exclude_zones = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Ausgeschlossene Zonen',
        help_text='Liste von Zone-Codes die ausgeschlossen werden sollen'
    )

    # Tracking
    impressions = models.PositiveIntegerField(default=0, verbose_name='Impressionen')
    clicks = models.PositiveIntegerField(default=0, verbose_name='Klicks')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Einfache Anzeige'
        verbose_name_plural = 'Einfache Anzeigen'
        ordering = ['-created_at']

    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.title}"

    @property
    def ctr(self):
        """Click-Through-Rate berechnen"""
        if self.impressions == 0:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)

    def get_primary_color(self):
        """Gibt die Primärfarbe basierend auf dem Farbschema zurück"""
        if self.color_scheme == 'custom' and self.custom_color:
            return self.custom_color

        color_map = {
            'blue': '#3b82f6',
            'green': '#10b981',
            'purple': '#8b5cf6',
            'orange': '#f97316',
            'red': '#ef4444',
            'teal': '#14b8a6',
            'pink': '#ec4899',
            'gray': '#6b7280',
        }
        return color_map.get(self.color_scheme, '#3b82f6')

    def is_allowed_in_zone(self, zone_code):
        """Prüft ob die Anzeige in einer Zone angezeigt werden darf"""
        if not self.exclude_zones:
            return True
        return zone_code not in self.exclude_zones

    def is_within_schedule(self):
        """Prüft ob die Anzeige innerhalb des Zeitplans liegt"""
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def is_allowed_for_user(self, user):
        """Prüft ob die Anzeige für diesen User sichtbar sein soll"""
        if self.target_audience == 'all':
            return True
        if self.target_audience == 'logged_in':
            return user.is_authenticated
        if self.target_audience == 'anonymous':
            return not user.is_authenticated
        return True

    def is_allowed_in_app(self, app_name):
        """Prüft ob die Anzeige in dieser App angezeigt werden darf"""
        # "__other__" = Seiten ohne App (Startseite, etc.)
        effective_app = app_name if app_name else '__other__'

        # Ausgeschlossene Apps
        if self.exclude_apps and effective_app in self.exclude_apps:
            return False

        # App-Filter (wenn gesetzt, nur diese Apps erlaubt)
        if self.app_filter:
            if effective_app not in self.app_filter:
                return False
        return True

    def get_badge_text(self):
        """Gibt den Badge-Text zurück"""
        if self.badge == 'custom':
            return self.badge_custom_text
        return self.badge.upper() if self.badge else ''

    def get_visual(self):
        """Gibt das visuelle Element zurück (Bild, Icon oder Video)"""
        if self.video_url:
            return {'type': 'video', 'url': self.video_url}
        if self.image:
            return {'type': 'image', 'url': self.image.url}
        if self.icon:
            return {'type': 'icon', 'class': self.icon}
        return None

    def record_impression(self):
        """Impression zählen"""
        SimpleAd.objects.filter(pk=self.pk).update(impressions=models.F('impressions') + 1)

    def record_click(self):
        """Click zählen"""
        SimpleAd.objects.filter(pk=self.pk).update(clicks=models.F('clicks') + 1)

    @classmethod
    def get_random_ad(cls, zone_code=None, user=None, app_name=None):
        """
        Holt eine zufällige aktive Anzeige (gewichtet).
        Berücksichtigt alle Filter: Zone, User, App, Zeitplanung
        """
        import random
        import logging
        logger = logging.getLogger('loomads')

        ads = list(cls.objects.filter(is_active=True))
        logger.debug(f"[SimpleAd] Suche Ads für zone={zone_code}, app={app_name}, user={user}")
        logger.debug(f"[SimpleAd] Gefunden: {len(ads)} aktive Ads")

        # Alle Filter anwenden
        filtered_ads = []
        for ad in ads:
            # Zeitplanung
            if not ad.is_within_schedule():
                logger.debug(f"[SimpleAd] {ad.title}: Außerhalb Zeitplan")
                continue
            # Zone
            if zone_code and not ad.is_allowed_in_zone(zone_code):
                logger.debug(f"[SimpleAd] {ad.title}: Zone {zone_code} ausgeschlossen")
                continue
            # User/Zielgruppe
            if user and not ad.is_allowed_for_user(user):
                logger.debug(f"[SimpleAd] {ad.title}: User nicht erlaubt (target={ad.target_audience})")
                continue
            # App
            if app_name and not ad.is_allowed_in_app(app_name):
                logger.debug(f"[SimpleAd] {ad.title}: App {app_name} nicht erlaubt")
                continue
            filtered_ads.append(ad)
            logger.debug(f"[SimpleAd] {ad.title}: ✓ Passend")

        if not filtered_ads:
            logger.debug(f"[SimpleAd] Keine passenden Ads gefunden!")
            return None

        # Gewichtete Auswahl
        weights = [ad.weight for ad in filtered_ads]
        selected = random.choices(filtered_ads, weights=weights, k=1)[0]
        logger.debug(f"[SimpleAd] Ausgewählt: {selected.title}")
        return selected

    @classmethod
    def get_ab_test_winner(cls, group_name):
        """
        Gibt die Anzeige mit der besten CTR aus einer A/B-Test-Gruppe zurück
        """
        ads = cls.objects.filter(
            is_active=True,
            ab_test_group=group_name
        ).exclude(ab_test_group='')

        if not ads:
            return None

        # Sortiere nach CTR
        best_ad = max(ads, key=lambda ad: ad.ctr)
        return best_ad
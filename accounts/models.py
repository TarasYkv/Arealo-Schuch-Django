from django.contrib.auth.models import AbstractUser
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField
from django.db.models import Sum, Q


class CustomUser(AbstractUser):
    """Erweiterte User-Model für benutzerdefinierte Ampel-Kategorien."""
    use_custom_categories = models.BooleanField(default=False, verbose_name="Benutzerdefinierte Kategorien verwenden")
    enable_ai_keyword_expansion = models.BooleanField(default=False, verbose_name="KI-Keyword-Erweiterung aktivieren")
    
    openai_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="OpenAI API Key")
    anthropic_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="Anthropic API Key")
    google_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="Google API Key")
    youtube_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="YouTube API Key")
    
    # Firmeninfo-Felder für Naturmacher
    company_info = models.TextField(blank=True, verbose_name="Firmeninformationen", 
                                   help_text="Beschreibung Ihres Unternehmens, Produkte, Zielgruppe, etc.")
    learning_goals = models.TextField(blank=True, verbose_name="Standard-Lernziele",
                                     help_text="Ihre Standard-Lernziele für Schulungen")
    
    # Profilbild
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, 
                                       verbose_name="Profilbild")
    
    # Super User für Bug-Chat
    is_bug_chat_superuser = models.BooleanField(default=False, verbose_name="Bug-Chat Super User",
                                               help_text="Kann Bug-Chat-Nachrichten empfangen und Super User verwalten")
    receive_bug_reports = models.BooleanField(default=False, verbose_name="Bug-Meldungen empfangen",
                                             help_text="Erhält Bug-Meldungen über das Chat-System")
    receive_anonymous_reports = models.BooleanField(default=False, verbose_name="Anonyme Meldungen empfangen",
                                                   help_text="Erhält auch Bug-Meldungen ohne angemeldeten User")
    
    # Online-Status
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Letzte Aktivität")
    is_online = models.BooleanField(default=False, verbose_name="Online")
    
    # Call-Berechtigungen
    can_make_audio_calls = models.BooleanField(default=True, verbose_name="Darf Audioanrufe tätigen")
    can_make_video_calls = models.BooleanField(default=True, verbose_name="Darf Videoanrufe tätigen")
    can_receive_audio_calls = models.BooleanField(default=True, verbose_name="Darf Audioanrufe empfangen")
    can_receive_video_calls = models.BooleanField(default=True, verbose_name="Darf Videoanrufe empfangen")
    
    # App-Freigabe Berechtigung
    can_manage_app_permissions = models.BooleanField(default=False, verbose_name="Darf App-Freigaben verwalten",
                                                   help_text="Erlaubt dem Benutzer das App-Freigabe Tab zu sehen und zu verwalten")
    
    # Design-Einstellungen
    dark_mode = models.BooleanField(default=False, verbose_name="Dunkles Design aktivieren")
    
    def __str__(self):
        return self.username
    
    def get_unread_chat_count(self):
        """Gibt die Anzahl ungelesener Chat-Nachrichten zurück"""
        from chat.models import ChatRoom
        
        total_unread = 0
        for room in self.chat_rooms.all():
            total_unread += room.get_unread_count(self)
        return total_unread
    
    def is_currently_online(self):
        """Prüft ob der User als online betrachtet wird (letzte Aktivität < 5 Minuten)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.last_activity:
            return False
        
        # Check if user was active in the last 5 minutes AND is marked as online
        is_recently_active = timezone.now() - self.last_activity < timedelta(minutes=5)
        
        # If user is not recently active, mark them as offline
        if not is_recently_active and self.is_online:
            self.is_online = False
            self.save(update_fields=['is_online'])
            
        return is_recently_active and self.is_online


class AmpelCategory(models.Model):
    """Benutzerdefinierte Ampel-Kategorien."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ampel_categories')
    name = models.CharField(max_length=100, verbose_name="Kategorie-Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ampel-Kategorie"
        verbose_name_plural = "Ampel-Kategorien"
        unique_together = ['user', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"


class CategoryKeyword(models.Model):
    """Suchbegriffe für jede Kategorie."""
    category = models.ForeignKey(AmpelCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=200, verbose_name="Suchbegriff")
    weight = models.PositiveIntegerField(default=1, verbose_name="Gewichtung")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Kategorie-Suchbegriff"
        verbose_name_plural = "Kategorie-Suchbegriffe"
        unique_together = ['category', 'keyword']
        ordering = ['-weight', 'keyword']
    
    def __str__(self):
        return f"{self.category.name}: {self.keyword}"


class UserLoginHistory(models.Model):
    """Trackt Login/Logout Zeiten für Benutzer"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True, verbose_name="Login Zeit")
    logout_time = models.DateTimeField(null=True, blank=True, verbose_name="Logout Zeit")
    session_duration = models.DurationField(null=True, blank=True, verbose_name="Session Dauer")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-Adresse")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    is_active_session = models.BooleanField(default=True, verbose_name="Aktive Session")
    
    class Meta:
        verbose_name = "Benutzer Login Historie"
        verbose_name_plural = "Benutzer Login Historien"
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time.strftime('%d.%m.%Y %H:%M')}"
    
    def get_duration_display(self):
        """Gibt die Session-Dauer in lesbarer Form zurück"""
        if self.session_duration:
            total_seconds = int(self.session_duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "Läuft noch"


class AppPermission(models.Model):
    """Definiert Zugriffsrechte für verschiedene Apps und Funktionen"""
    
    # App/Funktion Choices
    APP_CHOICES = [
        # Hauptkategorien
        ('schulungen', 'Schulungen'),
        ('shopify', 'Shopify'),
        ('bilder', 'Bilder'),
        ('todos', 'ToDos'),
        ('chat', 'Chat'),
        ('organisation', 'Organisation'),
        ('editor', 'Editor'),
        ('videos', 'Videos'),
        
        # Schuch Tools
        ('schuch', 'Schuch'),
        ('wirtschaftlichkeitsrechner', 'Wirtschaftlichkeitsrechner'),
        ('sportplatz_konfigurator', 'Sportplatz-Konfigurator'),
        ('pdf_suche', 'PDF-Suche'),
        ('ki_zusammenfassung', 'KI-Zusammenfassung'),
        
        # Shopify Unterkategorien
        ('shopify_produkte', 'Shopify - Produkte'),
        ('shopify_blogs', 'Shopify - Blogs'),
        ('shopify_seo_dashboard', 'Shopify - SEO Dashboard'),
        ('shopify_verkaufszahlen', 'Shopify - Verkaufszahlen'),
        ('shopify_seo_optimierung', 'Shopify - SEO-Optimierung'),
        ('shopify_alt_text', 'Shopify - Alt-Text Manager'),
        
        # Organisation Unterkategorien
        ('organisation_notizen', 'Organisation - Notizen'),
        ('organisation_termine', 'Organisation - Termine'),
        ('organisation_ideenboards', 'Organisation - Ideenboards'),
        ('organisation_terminanfragen', 'Organisation - Ausstehende Terminanfragen'),
    ]
    
    # Zugriffsebenen
    ACCESS_LEVEL_CHOICES = [
        ('blocked', 'Gesperrt'),
        ('anonymous', 'Nicht angemeldete Besucher'),
        ('authenticated', 'Angemeldete Nutzer'),
        ('selected', 'Ausgewählte Nutzer'),
    ]
    
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, unique=True, verbose_name="App/Funktion")
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='blocked', verbose_name="Zugriffsebene")
    selected_users = models.ManyToManyField(CustomUser, blank=True, related_name='app_permissions', 
                                          verbose_name="Ausgewählte Nutzer",
                                          help_text="Nur relevant wenn Zugriffsebene 'Ausgewählte Nutzer' ist")
    hide_in_frontend = models.BooleanField(default=False, verbose_name="Im Frontend ausblenden",
                                         help_text="App wird in Navigation und UI nicht angezeigt, auch wenn zugänglich")
    superuser_bypass = models.BooleanField(default=True, verbose_name="Superuser können immer zugreifen",
                                         help_text="Superuser haben unabhängig von den Einstellungen vollen Zugriff")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "App-Berechtigung"
        verbose_name_plural = "App-Berechtigungen"
        ordering = ['app_name']
    
    def __str__(self):
        return f"{self.get_app_name_display()} - {self.get_access_level_display()}"
    
    def has_access(self, user=None, check_frontend_visibility=False):
        """Prüft ob ein Benutzer Zugriff auf diese App hat"""
        if not self.is_active:
            return False
        
        # Superuser-Bypass: Superuser haben immer Zugriff (außer explizit deaktiviert)
        if user and user.is_authenticated and user.is_superuser and self.superuser_bypass:
            return True
            
        # Frontend-Sichtbarkeit prüfen (nur für UI-Anzeige)
        if check_frontend_visibility and self.hide_in_frontend:
            # Auch für Superuser ausblenden wenn explizit gewünscht
            if not (user and user.is_superuser):
                return False
            
        if self.access_level == 'blocked':
            return False
        elif self.access_level == 'anonymous':
            return True
        elif self.access_level == 'authenticated':
            return user and user.is_authenticated
        elif self.access_level == 'selected':
            return user and user.is_authenticated and self.selected_users.filter(id=user.id).exists()
        
        return False
    
    @classmethod
    def user_has_access(cls, app_name, user=None, check_frontend_visibility=False):
        """Klassenmethod um schnell zu prüfen ob ein User Zugriff auf eine App hat"""
        try:
            permission = cls.objects.get(app_name=app_name, is_active=True)
            return permission.has_access(user, check_frontend_visibility)
        except cls.DoesNotExist:
            # Wenn keine Berechtigung existiert, ist die App standardmäßig gesperrt
            # Außer für Superuser (haben immer Zugriff)
            if user and user.is_authenticated and user.is_superuser:
                return True
            return False
    
    @classmethod
    def user_can_see_in_frontend(cls, app_name, user=None):
        """Klassenmethod um zu prüfen ob eine App im Frontend angezeigt werden soll"""
        return cls.user_has_access(app_name, user, check_frontend_visibility=True)


class CustomPage(models.Model):
    """Model für benutzerdefinierte Seiten"""
    
    PAGE_TYPE_CHOICES = [
        ('landing', 'Landing Page'),
        ('about', 'Über uns'),
        ('services', 'Services/Leistungen'),
        ('contact', 'Kontakt'),
        ('blog', 'Blog/News'),
        ('gallery', 'Galerie'),
        ('custom', 'Benutzerdefiniert'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='custom_pages')
    page_name = models.CharField(max_length=50, verbose_name="Seiten-Name", 
                                help_text="Technischer Name für die URL")
    display_name = models.CharField(max_length=100, verbose_name="Anzeigename")
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, verbose_name="Seitentyp")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Benutzerdefinierte Seite"
        verbose_name_plural = "Benutzerdefinierte Seiten"
        unique_together = ['user', 'page_name']
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.user.username} - {self.display_name}"
    
    @classmethod
    def get_all_page_choices(cls, user):
        """Gibt alle verfügbaren Seiten für einen User zurück"""
        # Standard Seiten
        choices = [
            ('startseite', 'Startseite'),
        ]
        
        # Globale Bereiche
        choices.extend([
            ('header', '🔹 Header (global)'),
            ('footer', '🔹 Footer (global)'),
        ])
        
        # Benutzerdefinierte Seiten hinzufügen
        custom_pages = cls.objects.filter(user=user, is_active=True)
        for page in custom_pages:
            choices.append((page.page_name, page.display_name))
        
        return choices


class EditableContent(models.Model):
    """Model für bearbeitbare Inhalte auf Seiten"""
    
    # Wird dynamisch gefüllt basierend auf verfügbaren Seiten
    def get_page_choices(self):
        if hasattr(self, '_state') and self._state.adding:
            # Beim Erstellen - keine spezifischen Choices
            return []
        return CustomPage.get_all_page_choices(self.user if hasattr(self, 'user') else None)
    
    CONTENT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Bild'),
        ('hero_title', 'Hero Titel'),
        ('hero_subtitle', 'Hero Untertitel'),
        ('section_title', 'Bereich Titel'),
        ('section_text', 'Bereich Text'),
        ('button_text', 'Button Text'),
        ('testimonial', 'Kundenstimme'),
        ('html_block', 'HTML Block'),
        ('ai_generated', 'KI-generiert'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='editable_contents')
    page = models.CharField(max_length=50, verbose_name="Seite")
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE_CHOICES, verbose_name="Inhaltstyp")
    content_key = models.CharField(max_length=100, verbose_name="Inhalt Schlüssel", 
                                  help_text="Eindeutige Bezeichnung für diesen Inhalt")
    text_content = models.TextField(blank=True, verbose_name="Text Inhalt")
    html_content = models.TextField(blank=True, verbose_name="HTML Inhalt")
    css_content = models.TextField(blank=True, verbose_name="CSS Styles")
    ai_prompt = models.TextField(blank=True, verbose_name="KI Prompt", 
                               help_text="Beschreibung für KI-generierte Inhalte")
    image_content = models.ImageField(upload_to='editable_content/', blank=True, null=True, 
                                    verbose_name="Bild Inhalt")
    image_alt_text = models.CharField(max_length=255, blank=True, verbose_name="Bild Alt-Text")
    link_url = models.URLField(blank=True, verbose_name="Link URL")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Sortierreihenfolge")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Bearbeitbarer Inhalt"
        verbose_name_plural = "Bearbeitbare Inhalte"
        unique_together = ['user', 'page', 'content_key']
        ordering = ['page', 'sort_order', 'created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.page} - {self.content_key}"
    
    def get_display_content(self):
        """Gibt den anzuzeigenden Inhalt zurück"""
        if self.content_type == 'image' and self.image_content:
            return self.image_content.url
        elif self.content_type in ['html_block', 'ai_generated'] and self.html_content:
            return self.html_content
        return self.text_content or ""
    
    def get_css_styles(self):
        """Gibt die CSS-Styles zurück"""
        return self.css_content or ""


class SEOSettings(models.Model):
    """Model für SEO-Einstellungen pro Seite"""
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='seo_settings')
    page = models.CharField(max_length=50, verbose_name="Seite")
    seo_title = models.CharField(max_length=60, blank=True, verbose_name="SEO Titel", 
                                help_text="Empfohlen: 50-60 Zeichen")
    seo_description = models.TextField(max_length=160, blank=True, verbose_name="SEO Beschreibung",
                                     help_text="Empfohlen: 150-160 Zeichen")
    keywords = models.TextField(blank=True, verbose_name="Keywords",
                               help_text="Durch Kommas getrennt")
    canonical_url = models.URLField(blank=True, verbose_name="Canonical URL")
    noindex = models.BooleanField(default=False, verbose_name="Noindex",
                                 help_text="Seite von Suchmaschinen ausschließen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "SEO Einstellung"
        verbose_name_plural = "SEO Einstellungen"
        unique_together = ['user', 'page']
        
    def __str__(self):
        return f"{self.user.username} - {self.page} SEO"
    
    def get_title_length(self):
        return len(self.seo_title)
    
    def get_description_length(self):
        return len(self.seo_description)


class FeatureAccess(models.Model):
    """Definiert welche Apps/Features mit welchen Abonnements verfügbar sind"""
    
    # Subscription Types
    SUBSCRIPTION_REQUIRED_CHOICES = [
        ('free', 'Kostenlos verfügbar'),
        ('any_paid', 'Beliebiges bezahltes Abo erforderlich'),
        ('founder_access', 'Founder\'s Early Access erforderlich'),
        ('storage_plan', 'Storage-Plan erforderlich'),
        ('blocked', 'Komplett gesperrt'),
    ]
    
    # App Names - basierend auf den URLs und vorhandenen Apps
    APP_CHOICES = [
        # Hauptkategorien
        ('chat', 'Chat'),
        ('videos', 'Videos'), 
        ('shopify_manager', 'Shopify Manager'),
        ('image_editor', 'Bild Editor'),
        ('naturmacher', 'Schulungen (Naturmacher)'),
        ('organization', 'Organisation'),
        ('todos', 'ToDos'),
        ('pdf_sucher', 'PDF-Suche'),
        ('amortization_calculator', 'Wirtschaftlichkeitsrechner'),
        ('sportplatzApp', 'Sportplatz-Konfigurator'),
        ('bug_report', 'Bug Report'),
        ('payments', 'Zahlungen & Abos'),
        ('core', 'Schuch (Startseite/Kern)'),
        
        # Spezifische Features/Sub-Bereiche
        ('video_upload', 'Video Upload'),
        ('video_sharing', 'Video Sharing'),
        ('ai_features', 'KI-Features'),
        ('premium_support', 'Premium Support'),
        ('advanced_analytics', 'Erweiterte Analytik'),
    ]
    
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, unique=True, verbose_name="App/Feature")
    subscription_required = models.CharField(
        max_length=20, 
        choices=SUBSCRIPTION_REQUIRED_CHOICES, 
        default='free',
        verbose_name="Erforderliches Abonnement"
    )
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    show_upgrade_prompt = models.BooleanField(default=True, verbose_name="Upgrade-Hinweis anzeigen")
    upgrade_message = models.TextField(
        blank=True, 
        verbose_name="Upgrade-Nachricht",
        help_text="Benutzerdefinierte Nachricht für Upgrade-Prompt"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Feature-Zugriff"
        verbose_name_plural = "Feature-Zugriffe"
        ordering = ['app_name']
    
    def __str__(self):
        return f"{self.get_app_name_display()} - {self.get_subscription_required_display()}"
    
    def get_parent_app(self):
        """Gibt die übergeordnete App zurück, falls es sich um ein Sub-Feature handelt"""
        feature_to_parent_map = {
            'video_upload': 'videos',
            'video_sharing': 'videos',
            'ai_features': 'system',  # Systemweite KI-Features
            'premium_support': 'system',  # Systemweiter Support
            'advanced_analytics': 'system',  # Systemweite Analytik
        }
        return feature_to_parent_map.get(self.app_name, None)
    
    def get_display_name_with_parent(self):
        """Gibt den Anzeigenamen mit übergeordneter App zurück"""
        parent = self.get_parent_app()
        display_name = self.get_app_name_display()
        
        if parent:
            parent_names = {
                'videos': 'Videos',
                'system': 'System',
            }
            parent_display = parent_names.get(parent, parent)
            return f"{display_name} ({parent_display})"
        
        return display_name
    
    def user_has_access(self, user):
        """Prüft ob ein Benutzer Zugriff auf diese App/Feature hat"""
        if not self.is_active:
            return False
        
        # Superuser haben immer Zugriff
        if user and user.is_authenticated and user.is_superuser:
            return True
        
        # Kostenlos verfügbar
        if self.subscription_required == 'free':
            return True
        
        # Komplett gesperrt
        if self.subscription_required == 'blocked':
            return False
        
        # Benutzer muss angemeldet sein für alle anderen Optionen
        if not user or not user.is_authenticated:
            return False
        
        # Import hier um zirkuläre Imports zu vermeiden
        from payments.feature_access import FeatureAccessService
        
        if self.subscription_required == 'founder_access':
            return FeatureAccessService.has_founder_access(user)
        elif self.subscription_required == 'any_paid':
            return FeatureAccessService.has_premium_access(user)
        elif self.subscription_required == 'storage_plan':
            # Prüfe ob User einen Storage-Plan hat
            subscription = FeatureAccessService.get_user_active_subscription(user)
            return subscription and subscription.plan.plan_type == 'storage' and subscription.plan.price > 0
        
        return False
    
    def get_upgrade_message(self):
        """Gibt die Upgrade-Nachricht zurück"""
        if self.upgrade_message:
            return self.upgrade_message
        
        # Standard-Nachrichten basierend auf erforderlichem Abo
        messages = {
            'founder_access': 'Diese Funktion ist nur mit dem WorkLoom - Founder\'s Early Access verfügbar.',
            'any_paid': 'Diese Funktion erfordert ein bezahltes Abonnement.',
            'storage_plan': 'Diese Funktion erfordert einen Storage-Plan.',
            'blocked': 'Diese Funktion ist derzeit nicht verfügbar.',
        }
        return messages.get(self.subscription_required, 'Ein Upgrade ist erforderlich um diese Funktion zu nutzen.')
    
    @classmethod
    def user_can_access_app(cls, app_name, user):
        """Klassenmethod um schnell zu prüfen ob ein User auf eine App zugreifen kann"""
        try:
            feature = cls.objects.get(app_name=app_name, is_active=True)
            return feature.user_has_access(user)
        except cls.DoesNotExist:
            # Wenn keine FeatureAccess-Regel existiert, prüfe alte AppPermission
            if AppPermission.objects.filter(app_name=app_name).exists():
                return AppPermission.user_has_access(app_name, user)
            
            # Standard: Kostenlos verfügbar für angemeldete Benutzer
            return user and user.is_authenticated
    
    @classmethod
    def get_user_accessible_apps(cls, user):
        """Gibt alle Apps zurück auf die der Benutzer zugreifen kann"""
        accessible_apps = []
        
        for app_choice in cls.APP_CHOICES:
            app_name = app_choice[0]
            if cls.user_can_access_app(app_name, user):
                accessible_apps.append(app_name)
        
        return accessible_apps
    
    @classmethod
    def setup_default_access_rules(cls):
        """Erstellt Standard-Zugriffsregeln für alle Apps"""
        default_rules = [
            # Kostenlose Apps
            ('chat', 'free', 'Basis-Chat verfügbar für alle Benutzer'),
            ('videos', 'free', 'Video-Ansicht verfügbar, Upload erfordert Storage-Plan'),
            ('bug_report', 'free', 'Bug-Meldungen verfügbar für alle'),
            ('payments', 'free', 'Abo-Verwaltung verfügbar für alle'),
            
            # Founder's Early Access erforderlich
            ('shopify_manager', 'founder_access', 'Vollständiger Shopify-Manager nur mit Early Access'),
            ('image_editor', 'founder_access', 'Bild-Editor nur mit Early Access'),
            ('naturmacher', 'founder_access', 'Schulungs-Tools nur mit Early Access'),
            ('organization', 'founder_access', 'Organisations-Tools nur mit Early Access'),
            ('todos', 'founder_access', 'Erweiterte ToDo-Features nur mit Early Access'),
            ('pdf_sucher', 'founder_access', 'PDF-Suche nur mit Early Access'),
            ('amortization_calculator', 'founder_access', 'Wirtschaftlichkeitsrechner nur mit Early Access'),
            ('sportplatzApp', 'founder_access', 'Sportplatz-Konfigurator nur mit Early Access'),
            
            # Spezifische Features
            ('video_upload', 'storage_plan', 'Video-Upload erfordert Storage-Plan'),
            ('ai_features', 'founder_access', 'KI-Features nur mit Early Access'),
            ('premium_support', 'any_paid', 'Premium-Support für alle bezahlten Pläne'),
            ('advanced_analytics', 'founder_access', 'Erweiterte Analytik nur mit Early Access'),
        ]
        
        for app_name, subscription_required, description in default_rules:
            cls.objects.get_or_create(
                app_name=app_name,
                defaults={
                    'subscription_required': subscription_required,
                    'description': description,
                    'is_active': True,
                    'show_upgrade_prompt': True,
                }
            )
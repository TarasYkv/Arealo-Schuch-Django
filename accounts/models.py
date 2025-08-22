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
    desktop_view = models.BooleanField(default=False, verbose_name="Desktop-Ansicht erzwingen",
                                      help_text="Zeigt immer die Desktop-Version an, unabhängig vom Gerät")
    
    # E-Mail-Verifikation
    email_verified = models.BooleanField(default=False, verbose_name="E-Mail verifiziert")
    email_verification_token = models.CharField(max_length=100, blank=True, null=True, verbose_name="E-Mail Verifikationstoken")
    email_verification_sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Verifikations-E-Mail gesendet am")
    
    # KI-Model-Einstellungen
    preferred_openai_model = models.CharField(max_length=50, default='gpt-4o-mini', verbose_name="Bevorzugtes OpenAI Modell",
                                             choices=[
                                                 ('gpt-4o', 'GPT-4o (Premium)'),
                                                 ('gpt-4o-mini', 'GPT-4o Mini (Standard)'),
                                                 ('gpt-4-turbo', 'GPT-4 Turbo'),
                                                 ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Günstig)'),
                                             ])
    preferred_anthropic_model = models.CharField(max_length=50, default='claude-3-5-sonnet-20241022', verbose_name="Bevorzugtes Anthropic Modell",
                                                choices=[
                                                    ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet (Premium)'),
                                                    ('claude-3-5-haiku-20241022', 'Claude 3.5 Haiku (Schnell)'),
                                                    ('claude-3-opus-20240229', 'Claude 3 Opus (Top-Tier)'),
                                                    ('claude-3-sonnet-20240229', 'Claude 3 Sonnet (Standard)'),
                                                    ('claude-3-haiku-20240307', 'Claude 3 Haiku (Günstig)'),
                                                ])
    
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
        ('mail', 'Email'),
        ('email_templates', 'Email-Vorlagen'),
        ('somi_plan', 'SoMi-Plan'),
        ('makeads', 'AdsMake'),
        ('streamrec', 'StreamRec'),
        
        # Schuch Tools
        ('schuch', 'Schuch'),
        ('schuch_dashboard', 'Schuch Dashboard'),
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
        ('in_development', 'In Entwicklung'),
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
        elif self.access_level == 'in_development':
            # Apps in Entwicklung sind nur für Superuser zugänglich
            return user and user.is_authenticated and user.is_superuser
        
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


class UserAppPermission(models.Model):
    """Individuelle App-Berechtigungen pro Nutzer (überschreibt globale AppPermission-Einstellungen)"""
    
    OVERRIDE_CHOICES = [
        ('allow', 'Explizit erlauben'),
        ('deny', 'Explizit verweigern'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='individual_app_permissions',
                           verbose_name="Benutzer")
    app_name = models.CharField(max_length=50, choices=AppPermission.APP_CHOICES, verbose_name="App/Funktion")
    override_type = models.CharField(max_length=10, choices=OVERRIDE_CHOICES, verbose_name="Überschreibung")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='created_user_permissions', verbose_name="Erstellt von")
    
    class Meta:
        verbose_name = "Individuelle App-Berechtigung"
        verbose_name_plural = "Individuelle App-Berechtigungen"
        unique_together = ['user', 'app_name']
        ordering = ['user__username', 'app_name']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_app_name_display()} - {self.get_override_type_display()}"
    
    @classmethod
    def user_has_individual_permission(cls, app_name, user):
        """Prüft ob für einen Nutzer eine individuelle Berechtigung für eine App existiert"""
        if not user or not user.is_authenticated:
            return None
        
        try:
            permission = cls.objects.get(user=user, app_name=app_name, is_active=True)
            return permission.override_type == 'allow'
        except cls.DoesNotExist:
            return None  # Keine individuelle Berechtigung vorhanden
    
    @classmethod
    def get_user_app_access(cls, app_name, user):
        """
        Hauptfunktion um zu prüfen ob ein Nutzer Zugriff auf eine App hat.
        Priorität: Individuelle Berechtigung > Globale Berechtigung
        """
        # 1. Prüfe individuelle Berechtigung (höchste Priorität)
        individual_permission = cls.user_has_individual_permission(app_name, user)
        if individual_permission is not None:
            return individual_permission
        
        # 2. Fallback auf globale AppPermission
        return AppPermission.user_has_access(app_name, user)
    
    @classmethod
    def user_can_see_app_in_frontend(cls, app_name, user):
        """
        Prüft ob ein Nutzer eine App im Frontend sehen kann.
        Berücksichtigt individuelle Berechtigungen und hide_in_frontend Flag.
        """
        # 1. Prüfe individuelle Berechtigung (höchste Priorität)
        individual_permission = cls.user_has_individual_permission(app_name, user)
        if individual_permission is not None:
            # Bei expliziter Verweigerung wird die App nicht angezeigt
            if individual_permission == False:
                return False
            # Bei expliziter Erlaubnis prüfe trotzdem hide_in_frontend
            try:
                app_permission = AppPermission.objects.get(app_name=app_name)
                return not app_permission.hide_in_frontend
            except AppPermission.DoesNotExist:
                return True  # Wenn keine globale Permission existiert, zeige die App
        
        # 2. Fallback auf globale AppPermission mit Frontend-Sichtbarkeit
        return AppPermission.user_can_see_in_frontend(app_name, user)


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
        # Core/Standard Seiten
        choices = [
            ('startseite', '🏠 Startseite'),
            ('impressum', '📄 Impressum'),
            ('agb', '📄 AGB'),
            ('datenschutz', '🔒 Datenschutz'),
        ]
        
        # Globale Bereiche
        choices.extend([
            ('header', '🔹 Header (global)'),
            ('footer', '🔹 Footer (global)'),
        ])
        
        # App-Dashboard Seiten (nur wenn User Zugriff hat)
        if user and user.is_authenticated:
            app_pages = [
                ('accounts_dashboard', '👤 Account Dashboard'),
                ('mail_dashboard', '📧 Mail Dashboard'),
                ('shopify_dashboard', '🛒 Shopify Dashboard'),
                ('image_editor_dashboard', '🖼️ Bild-Editor Dashboard'),
                ('organization_dashboard', '📅 Organisation Dashboard'),
                ('naturmacher_dashboard', '🌱 Schulungen Dashboard'),
                ('videos_dashboard', '🎥 Videos Dashboard'),
                ('chat_dashboard', '💬 Chat Dashboard'),
                ('somi_plan_dashboard', '📊 SOMI Plan Dashboard'),
                ('email_templates_dashboard', '📨 E-Mail Templates Dashboard'),
            ]
            
            # Prüfe App-Berechtigungen (falls implementiert)
            for page_key, page_name in app_pages:
                choices.append((page_key, page_name))
        
        # Landing Pages & Marketing
        choices.extend([
            ('landing_about', '🌟 Über uns'),
            ('landing_services', '🔧 Services'),
            ('landing_pricing', '💰 Preise'),
            ('landing_contact', '📞 Kontakt'),
            ('landing_features', '⚡ Features'),
            ('landing_testimonials', '💬 Kundenstimmen'),
            ('landing_blog', '📝 Blog'),
            ('landing_faq', '❓ FAQ'),
        ])
        
        # E-Commerce Seiten
        choices.extend([
            ('shop_products', '🛍️ Produkte'),
            ('shop_categories', '📂 Kategorien'),
            ('shop_cart', '🛒 Warenkorb'),
            ('shop_checkout', '💳 Checkout'),
            ('shop_account', '👤 Kundenkonto'),
            ('shop_orders', '📦 Bestellungen'),
        ])
        
        # Funktionale Seiten
        choices.extend([
            ('search_results', '🔍 Suchergebnisse'),
            ('error_404', '❌ 404 Fehlerseite'),
            ('error_500', '⚠️ 500 Fehlerseite'),
            ('maintenance', '🔧 Wartungsseite'),
            ('coming_soon', '🚀 Bald verfügbar'),
        ])
        
        # Benutzerdefinierte Seiten hinzufügen
        if user:
            custom_pages = cls.objects.filter(user=user, is_active=True)
            if custom_pages.exists():
                choices.append(('', '--- Benutzerdefinierte Seiten ---'))
                for page in custom_pages:
                    choices.append((page.page_name, f'📝 {page.display_name}'))
        
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
    section = models.CharField(max_length=50, blank=True, verbose_name="Bereich", 
                              help_text="Kategorisierung des Inhalts (z.B. hero, features, pricing)")
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


class ZohoAPISettings(models.Model):
    """Model für Zoho Mail API-Einstellungen pro Benutzer"""
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='zoho_mail_settings')
    client_id = EncryptedCharField(max_length=255, blank=True, verbose_name="Zoho Client ID")
    client_secret = EncryptedCharField(max_length=255, blank=True, verbose_name="Zoho Client Secret")
    redirect_uri = models.URLField(blank=True, verbose_name="Redirect URI")
    region = models.CharField(max_length=5, choices=[('US', 'US'), ('EU', 'EU'), ('IN', 'India'), ('AU', 'Australia')], 
                             default='EU', verbose_name="Zoho Region")
    
    # OAuth2 Tokens (werden nach Autorisierung gefüllt)
    access_token = EncryptedCharField(max_length=1000, blank=True, null=True)
    refresh_token = EncryptedCharField(max_length=1000, blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    
    # Status und Konfiguration
    is_configured = models.BooleanField(default=False, verbose_name="Konfiguriert")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    last_test_success = models.DateTimeField(blank=True, null=True, verbose_name="Letzter erfolgreicher Test")
    last_error = models.TextField(blank=True, verbose_name="Letzter Fehler")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Zoho Mail API Einstellung"
        verbose_name_plural = "Zoho Mail API Einstellungen"
    
    def __str__(self):
        return f"{self.user.username} - Zoho Mail ({self.region})"
    
    @property
    def base_url(self):
        """Gibt die Basis-URL für die jeweilige Region zurück"""
        region_urls = {
            'US': 'https://mail.zoho.com/api/',
            'EU': 'https://mail.zoho.eu/api/',
            'IN': 'https://mail.zoho.in/api/',
            'AU': 'https://mail.zoho.com.au/api/',
        }
        return region_urls.get(self.region, region_urls['EU'])
    
    @property
    def auth_url(self):
        """Gibt die Autorisierungs-URL für die jeweilige Region zurück"""
        region_auth_urls = {
            'US': 'https://accounts.zoho.com/oauth/v2/auth',
            'EU': 'https://accounts.zoho.eu/oauth/v2/auth', 
            'IN': 'https://accounts.zoho.in/oauth/v2/auth',
            'AU': 'https://accounts.zoho.com.au/oauth/v2/auth',
        }
        return region_auth_urls.get(self.region, region_auth_urls['EU'])
    
    @property
    def token_url(self):
        """Gibt die Token-URL für die jeweilige Region zurück"""
        region_token_urls = {
            'US': 'https://accounts.zoho.com/oauth/v2/token',
            'EU': 'https://accounts.zoho.eu/oauth/v2/token',
            'IN': 'https://accounts.zoho.in/oauth/v2/token', 
            'AU': 'https://accounts.zoho.com.au/oauth/v2/token',
        }
        return region_token_urls.get(self.region, region_token_urls['EU'])
    
    def get_configuration_status(self):
        """Gibt den Konfigurationsstatus zurück"""
        if not self.client_id or not self.client_secret:
            return 'Nicht konfiguriert'
        elif not self.access_token:
            return 'Autorisierung erforderlich'
        elif self.last_test_success:
            return 'Konfiguriert und getestet'
        else:
            return 'Konfiguriert'


class AppUsageTracking(models.Model):
    """Trackt die Nutzung von Apps/Features pro Benutzer"""
    
    ACTIVITY_TYPE_CHOICES = [
        ('app_usage', 'App-Nutzung'),
        ('video_call', 'Videoanruf'),
        ('audio_call', 'Audioanruf'),
        ('screen_share', 'Bildschirmfreigabe'),
        ('file_upload', 'Datei-Upload'),
        ('chat_message', 'Chat-Nachricht'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='app_usage_logs')
    app_name = models.CharField(max_length=50, verbose_name="App/Feature Name")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES, default='app_usage', verbose_name="Aktivitätstyp")
    url_path = models.CharField(max_length=255, verbose_name="URL Pfad")
    session_start = models.DateTimeField(auto_now_add=True, verbose_name="Session Start")
    session_end = models.DateTimeField(null=True, blank=True, verbose_name="Session Ende")
    duration_seconds = models.IntegerField(default=0, verbose_name="Dauer in Sekunden")
    
    # Call-spezifische Felder
    call_participants = models.JSONField(default=list, blank=True, verbose_name="Anruf-Teilnehmer")
    call_quality_rating = models.IntegerField(null=True, blank=True, verbose_name="Anruf-Qualitätsbewertung (1-5)")
    
    # Zusätzliche Metadaten
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-Adresse")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    referrer = models.URLField(blank=True, verbose_name="Referrer URL")
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="Zusätzliche Daten")
    
    # Status
    is_active_session = models.BooleanField(default=True, verbose_name="Aktive Session")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "App-Nutzungs-Tracking"
        verbose_name_plural = "App-Nutzungs-Trackings"
        ordering = ['-session_start']
        indexes = [
            models.Index(fields=['user', 'app_name', 'session_start']),
            models.Index(fields=['session_start']),
            models.Index(fields=['is_active_session']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.app_name} ({self.session_start.strftime('%d.%m.%Y %H:%M')})"
    
    def end_session(self):
        """Beendet die aktuelle Session"""
        from django.utils import timezone
        if self.is_active_session:
            self.session_end = timezone.now()
            self.duration_seconds = int((self.session_end - self.session_start).total_seconds())
            self.is_active_session = False
            self.save()
    
    def get_duration_display(self):
        """Gibt die Dauer in lesbarer Form zurück"""
        if self.duration_seconds:
            hours, remainder = divmod(self.duration_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "Läuft noch..."
    
    def get_app_display_name(self):
        """Gibt den Anzeigenamen der App zurück"""
        app_name_mapping = {
            'chat': 'Chat',
            'videos': 'Videos',
            'mail': 'Email',
            'schuch': 'Schuch',
            'schuch_dashboard': 'Schuch Dashboard',
            'shopify_manager': 'Shopify Manager',
            'image_editor': 'Bild Editor',
            'naturmacher': 'Schulungen',
            'organization': 'Organisation',
            'todos': 'ToDos',
            'pdf_sucher': 'PDF-Suche',
            'amortization_calculator': 'Wirtschaftlichkeitsrechner',
            'sportplatzApp': 'Sportplatz-Konfigurator',
            'bug_report': 'Bug Report',
            'payments': 'Zahlungen & Abos',
            'accounts': 'Konto-Verwaltung',
        }
        return app_name_mapping.get(self.app_name, self.app_name.replace('_', ' ').title())
    
    @classmethod
    def get_user_app_statistics(cls, user, days=30):
        """Gibt umfassende App-Nutzungsstatistiken für einen Benutzer zurück"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg, Q
        
        start_date = timezone.now() - timedelta(days=days)
        
        # App-spezifische Statistiken
        app_stats = cls.objects.filter(
            user=user,
            session_start__gte=start_date
        ).values('app_name').annotate(
            total_sessions=Count('id'),
            total_duration=Sum('duration_seconds'),
            avg_duration=Avg('duration_seconds'),
            last_used=models.Max('session_start'),
            video_calls=Count('id', filter=Q(activity_type='video_call')),
            audio_calls=Count('id', filter=Q(activity_type='audio_call')),
            video_call_duration=Sum('duration_seconds', filter=Q(activity_type='video_call')),
            audio_call_duration=Sum('duration_seconds', filter=Q(activity_type='audio_call')),
        ).order_by('-total_duration')
        
        # Aktivitätstyp-Statistiken
        activity_stats = cls.objects.filter(
            user=user,
            session_start__gte=start_date
        ).values('activity_type').annotate(
            total_sessions=Count('id'),
            total_duration=Sum('duration_seconds'),
            avg_duration=Avg('duration_seconds')
        ).order_by('-total_duration')
        
        # Tägliche Aktivitätsstatistiken
        daily_stats = cls.objects.filter(
            user=user,
            session_start__gte=start_date
        ).extra(
            select={'day': 'date(session_start)'}
        ).values('day').annotate(
            sessions=Count('id'),
            duration=Sum('duration_seconds'),
            video_calls=Count('id', filter=Q(activity_type='video_call')),
            audio_calls=Count('id', filter=Q(activity_type='audio_call')),
            video_call_duration=Sum('duration_seconds', filter=Q(activity_type='video_call')),
            audio_call_duration=Sum('duration_seconds', filter=Q(activity_type='audio_call'))
        ).order_by('day')
        
        # Call-spezifische Statistiken
        call_stats = {
            'total_video_calls': cls.objects.filter(user=user, activity_type='video_call', session_start__gte=start_date).count(),
            'total_audio_calls': cls.objects.filter(user=user, activity_type='audio_call', session_start__gte=start_date).count(),
            'total_video_duration': cls.objects.filter(user=user, activity_type='video_call', session_start__gte=start_date).aggregate(total=Sum('duration_seconds'))['total'] or 0,
            'total_audio_duration': cls.objects.filter(user=user, activity_type='audio_call', session_start__gte=start_date).aggregate(total=Sum('duration_seconds'))['total'] or 0,
            'avg_video_call_duration': cls.objects.filter(user=user, activity_type='video_call', session_start__gte=start_date).aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
            'avg_audio_call_duration': cls.objects.filter(user=user, activity_type='audio_call', session_start__gte=start_date).aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
        }
        
        return {
            'app_stats': app_stats,
            'activity_stats': activity_stats,
            'daily_stats': daily_stats,
            'call_stats': call_stats,
            'total_sessions': cls.objects.filter(user=user, session_start__gte=start_date).count(),
            'total_duration': cls.objects.filter(user=user, session_start__gte=start_date).aggregate(
                total=Sum('duration_seconds')
            )['total'] or 0,
        }
    
    @classmethod
    def start_session(cls, user, app_name, url_path, request=None, activity_type='app_usage', **kwargs):
        """Startet eine neue App-Session oder Activity"""
        # Beende alle aktiven Sessions für diesen User zuerst (nur bei App-Nutzung)
        if activity_type == 'app_usage':
            active_sessions = cls.objects.filter(user=user, is_active_session=True, activity_type='app_usage')
            for session in active_sessions:
                session.end_session()
        
        # Erstelle neue Session
        session_data = {
            'user': user,
            'app_name': app_name,
            'activity_type': activity_type,
            'url_path': url_path,
        }
        
        # Zusätzliche Daten für Calls
        if activity_type in ['video_call', 'audio_call']:
            session_data.update({
                'call_participants': kwargs.get('participants', []),
                'extra_data': kwargs.get('extra_data', {}),
            })
        
        if request:
            session_data.update({
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'referrer': request.META.get('HTTP_REFERER', ''),
            })
        
        return cls.objects.create(**session_data)
    
    @classmethod
    def track_video_call(cls, user, participants=None, quality_rating=None, extra_data=None):
        """Trackt einen Videoanruf"""
        return cls.start_session(
            user=user,
            app_name='chat',
            url_path='/chat/video-call/',
            activity_type='video_call',
            participants=participants or [],
            extra_data=extra_data or {}
        )
    
    @classmethod
    def track_audio_call(cls, user, participants=None, quality_rating=None, extra_data=None):
        """Trackt einen Audioanruf"""
        return cls.start_session(
            user=user,
            app_name='chat',
            url_path='/chat/audio-call/',
            activity_type='audio_call',
            participants=participants or [],
            extra_data=extra_data or {}
        )


class AppInfo(models.Model):
    """Detaillierte Informationen über Apps/Features für Info-Seiten"""
    
    # App Names - based on FeatureAccess APP_CHOICES
    APP_CHOICES = [
        # Hauptkategorien
        ('chat', 'Chat'),
        ('videos', 'Videos'), 
        ('mail', 'Email'),
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
    ]
    
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, unique=True, verbose_name="App/Feature")
    title = models.CharField(max_length=200, verbose_name="Titel")
    short_description = models.CharField(max_length=300, verbose_name="Kurzbeschreibung")
    detailed_description = models.TextField(verbose_name="Detaillierte Beschreibung")
    
    # Features als JSON Field für flexible Liste
    key_features = models.JSONField(default=list, verbose_name="Hauptfunktionen", 
                                   help_text="Liste der wichtigsten Features als JSON Array")
    
    # Requirements
    subscription_requirements = models.TextField(blank=True, verbose_name="Abo-Anforderungen")
    technical_requirements = models.TextField(blank=True, verbose_name="Technische Anforderungen")
    
    # Visual content
    icon_class = models.CharField(max_length=100, default="bi bi-app", verbose_name="Icon CSS Klasse")
    screenshot_url = models.URLField(blank=True, verbose_name="Screenshot URL")
    
    # Status und Meta
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    development_status = models.CharField(max_length=50, default="stable", 
                                        choices=[
                                            ('development', 'In Entwicklung'),
                                            ('beta', 'Beta'),
                                            ('stable', 'Stabil'),
                                            ('deprecated', 'Veraltet')
                                        ], verbose_name="Entwicklungsstatus")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    class Meta:
        verbose_name = "App Information"
        verbose_name_plural = "App Informationen"
        ordering = ['title']
    
    def __str__(self):
        return f"{self.title} ({self.app_name})"


class FeatureAccess(models.Model):
    """Definiert welche Apps/Features mit welchen Abonnements verfügbar sind"""
    
    # Subscription Types
    SUBSCRIPTION_REQUIRED_CHOICES = [
        ('free', 'Kostenlos verfügbar'),
        ('any_paid', 'Beliebiges bezahltes Abo erforderlich'),
        ('founder_access', 'Founder\'s Early Access erforderlich'),
        ('storage_plan', 'Storage-Plan erforderlich'),
        ('in_development', 'In Entwicklung'),
        ('blocked', 'Komplett gesperrt'),
    ]
    
    # App Names - basierend auf den URLs und vorhandenen Apps
    APP_CHOICES = [
        # Hauptkategorien
        ('chat', 'Chat'),
        ('videos', 'Videos'), 
        ('mail', 'Email'),
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
        
        # In Entwicklung - nicht verfügbar (außer für Superuser, die oben bereits geprüft wurden)
        if self.subscription_required == 'in_development':
            return False
        
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
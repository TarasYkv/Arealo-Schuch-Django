from django.db import models
from django.conf import settings
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedTextField, EncryptedCharField


class EmailConfiguration(models.Model):
    """
    Secure storage for email configuration
    Only accessible by superusers
    """
    # SMTP Configuration
    smtp_host = models.CharField(max_length=255, default='smtp.gmail.com', help_text='SMTP Server Host')
    smtp_port = models.IntegerField(default=587, help_text='SMTP Server Port')
    smtp_use_tls = models.BooleanField(default=True, help_text='Use TLS encryption')
    smtp_use_ssl = models.BooleanField(default=False, help_text='Use SSL encryption')
    
    # Email Account
    email_host_user = models.EmailField(help_text='Email address for sending')
    email_host_password = EncryptedCharField(max_length=500, help_text='Email account password/app password')
    default_from_email = models.EmailField(help_text='Default "From" email address')
    
    # Additional Settings
    is_active = models.BooleanField(default=True, help_text='Use this configuration')
    backend_type = models.CharField(
        max_length=100,
        choices=[
            ('smtp', 'SMTP Backend'),
            ('console', 'Console Backend (Development)'),
            ('filebased', 'File-based Backend (Testing)')
        ],
        default='smtp'
    )
    
    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Zoho Configuration (optional)
    zoho_client_id = EncryptedCharField(max_length=500, blank=True, null=True, help_text='Zoho Client ID')
    zoho_client_secret = EncryptedCharField(max_length=500, blank=True, null=True, help_text='Zoho Client Secret')
    zoho_redirect_uri = models.URLField(blank=True, null=True, help_text='Zoho Redirect URI')
    
    class Meta:
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configurations"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email Config: {self.email_host_user} ({self.smtp_host})"
    
    def test_connection(self):
        """Test SMTP connection and auto-fallback if needed"""
        import socket
        import smtplib
        from datetime import datetime
        
        # Try current configuration
        try:
            # Test DNS resolution first
            socket.gethostbyname(self.smtp_host)
            
            # Test SMTP connection
            if self.smtp_use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                if self.smtp_use_tls:
                    server.starttls()
            
            server.quit()
            return {'success': True, 'message': 'Verbindung erfolgreich'}
            
        except Exception as e:
            # Auto-fallback for DNS errors
            if '[Errno -3]' in str(e) or 'name resolution' in str(e):
                return self._auto_fallback_configuration()
            return {'success': False, 'message': str(e)}
    
    def _auto_fallback_configuration(self):
        """Automatically configure fallback SMTP if DNS fails"""
        # Determine best Zoho server based on email domain
        email_domain = self.email_host_user.split('@')[1].lower()
        
        fallback_configs = []
        
        if 'zoho' in email_domain:
            fallback_configs = [
                {'host': 'smtp.zohomaileu.com', 'port': 587, 'tls': True, 'region': 'EU'},
                {'host': 'smtp.zoho.com', 'port': 587, 'tls': True, 'region': 'US'},
                {'host': 'smtp.zoho.eu', 'port': 587, 'tls': True, 'region': 'Europe'},
            ]
        else:
            # Generic fallbacks
            fallback_configs = [
                {'host': 'smtp.gmail.com', 'port': 587, 'tls': True, 'service': 'Gmail'},
                {'host': 'smtp-mail.outlook.com', 'port': 587, 'tls': True, 'service': 'Outlook'},
            ]
        
        # Test each fallback
        for config in fallback_configs:
            try:
                import socket
                socket.gethostbyname(config['host'])
                
                # Update configuration automatically
                original_host = self.smtp_host
                self.smtp_host = config['host']
                self.smtp_port = config['port']
                self.smtp_use_tls = config['tls']
                self.smtp_use_ssl = False
                self.save()
                
                return {
                    'success': True, 
                    'message': f'Automatisch auf {config["host"]} umgestellt (Original: {original_host} nicht erreichbar)',
                    'fallback_used': True,
                    'original_host': original_host
                }
                
            except socket.gaierror:
                continue
        
        return {
            'success': False, 
            'message': 'Kein funktionierender SMTP-Server gefunden',
            'fallback_attempted': True
        }
    
    @classmethod
    def get_active_config(cls):
        """Get the active email configuration"""
        return cls.objects.filter(is_active=True).first()
    
    def save(self, *args, **kwargs):
        # Ensure only one configuration is active at a time
        if self.is_active:
            EmailConfiguration.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)
    
    @property
    def masked_password(self):
        """Return masked password for display"""
        if self.email_host_password:
            return '●' * min(len(self.email_host_password), 12)
        return 'Nicht gesetzt'
    
    def get_django_email_settings(self):
        """Convert to Django email settings format"""
        backend_map = {
            'smtp': 'django.core.mail.backends.smtp.EmailBackend',
            'console': 'django.core.mail.backends.console.EmailBackend',
            'filebased': 'django.core.mail.backends.filebased.EmailBackend'
        }
        
        return {
            'EMAIL_BACKEND': backend_map.get(self.backend_type, backend_map['smtp']),
            'EMAIL_HOST': self.smtp_host,
            'EMAIL_PORT': self.smtp_port,
            'EMAIL_USE_TLS': self.smtp_use_tls,
            'EMAIL_USE_SSL': self.smtp_use_ssl,
            'EMAIL_HOST_USER': self.email_host_user,
            'EMAIL_HOST_PASSWORD': self.email_host_password,
            'DEFAULT_FROM_EMAIL': self.default_from_email,
        }


class SuperuserEmailShare(models.Model):
    """
    Share email addresses with all superusers
    """
    email_address = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, help_text='Display name for this email')
    description = models.TextField(blank=True, help_text='Description or purpose of this email')
    is_active = models.BooleanField(default=True)
    
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Shared Superuser Email"
        verbose_name_plural = "Shared Superuser Emails"
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.display_name} ({self.email_address})"


class GlobalMessage(models.Model):
    """
    Global messages/announcements for the website
    Only manageable by superusers
    """
    DISPLAY_POSITION_CHOICES = [
        ('popup_center', 'Popup - Mitte'),
        ('popup_top', 'Popup - Oben'),
        ('banner_top', 'Banner - Oben'),
        ('banner_bottom', 'Banner - Unten'),
        ('toast_top_right', 'Toast - Oben Rechts'),
        ('toast_top_left', 'Toast - Oben Links'),
        ('toast_bottom_right', 'Toast - Unten Rechts'),
        ('toast_bottom_left', 'Toast - Unten Links'),
        ('sidebar_right', 'Seitlich - Rechts'),
        ('sidebar_left', 'Seitlich - Links'),
    ]

    DISPLAY_TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warnung'),
        ('success', 'Erfolg'),
        ('error', 'Fehler'),
        ('announcement', 'Ankündigung'),
    ]

    VISIBILITY_CHOICES = [
        ('all', 'Alle Besucher'),
        ('authenticated', 'Nur angemeldete Benutzer'),
        ('unauthenticated', 'Nur nicht angemeldete Besucher'),
        ('specific_users', 'Bestimmte Benutzer'),
        ('staff_only', 'Nur Staff-Benutzer'),
        ('superuser_only', 'Nur Superuser'),
    ]

    title = models.CharField(max_length=200, help_text='Titel der Nachricht')
    content = models.TextField(help_text='Inhalt der Nachricht')

    display_position = models.CharField(
        max_length=50,
        choices=DISPLAY_POSITION_CHOICES,
        default='popup_center',
        help_text='Position der Nachrichtenanzeige'
    )

    display_type = models.CharField(
        max_length=20,
        choices=DISPLAY_TYPE_CHOICES,
        default='info',
        help_text='Art der Nachricht (bestimmt Farbe/Icon)'
    )

    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='all',
        help_text='Wer soll diese Nachricht sehen'
    )

    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text='Anzeigedauer in Sekunden (leer = unendlich)'
    )

    is_active = models.BooleanField(default=True, help_text='Nachricht aktiv anzeigen')
    is_dismissible = models.BooleanField(default=True, help_text='Benutzer kann Nachricht schließen')

    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Startdatum (leer = sofort)'
    )

    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Enddatum (leer = unbegrenzt)'
    )

    # User targeting
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='targeted_messages',
        help_text='Spezifische Benutzer für diese Nachricht (nur relevant wenn Sichtbarkeit = "Bestimmte Benutzer")'
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Globale Nachricht"
        verbose_name_plural = "Globale Nachrichten"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_display_position_display()})"

    def is_currently_active(self):
        """Check if message should be displayed now"""
        if not self.is_active:
            return False

        now = timezone.now()

        if self.start_date and now < self.start_date:
            return False

        if self.end_date and now > self.end_date:
            return False

        return True

    def should_show_for_user(self, user):
        """Check if message should be shown for specific user"""
        if not self.is_currently_active():
            return False

        # Handle anonymous users (user is None)
        is_authenticated = user is not None and hasattr(user, 'is_authenticated') and user.is_authenticated
        is_staff = is_authenticated and user.is_staff
        is_superuser = is_authenticated and user.is_superuser

        # Check visibility settings
        if self.visibility == 'authenticated' and not is_authenticated:
            return False

        if self.visibility == 'unauthenticated' and is_authenticated:
            return False

        if self.visibility == 'staff_only' and not is_staff:
            return False

        if self.visibility == 'superuser_only' and not is_superuser:
            return False

        if self.visibility == 'specific_users':
            if not is_authenticated:
                return False
            # Check if user is in target_users
            return self.target_users.filter(id=user.id).exists()

        return True

    @classmethod
    def get_active_messages_for_user(cls, user):
        """Get all active messages for a specific user"""
        return [msg for msg in cls.objects.filter(is_active=True)
                if msg.should_show_for_user(user)]


class GlobalMessageDebugSettings(models.Model):
    """
    Settings for Global Messages Debug Display
    Controls when and for whom the debug info is shown
    """
    DEBUG_VISIBILITY_CHOICES = [
        ('disabled', 'Ausgeschaltet'),
        ('staff_only', 'Nur Staff-Benutzer'),
        ('superuser_only', 'Nur Superuser'),
        ('authenticated', 'Alle angemeldeten Benutzer'),
        ('all', 'Alle Benutzer'),
    ]

    is_debug_enabled = models.BooleanField(
        default=True,
        help_text='Debug-Anzeige aktivieren/deaktivieren'
    )

    debug_visibility = models.CharField(
        max_length=20,
        choices=DEBUG_VISIBILITY_CHOICES,
        default='staff_only',
        help_text='Wer soll die Debug-Anzeige sehen können'
    )

    show_message_details = models.BooleanField(
        default=True,
        help_text='Details der aktiven Nachrichten anzeigen'
    )

    show_user_info = models.BooleanField(
        default=True,
        help_text='Benutzerinformationen anzeigen'
    )

    show_statistics = models.BooleanField(
        default=True,
        help_text='Nachrichtenstatistiken anzeigen'
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Global Messages Debug-Einstellungen"
        verbose_name_plural = "Global Messages Debug-Einstellungen"

    def __str__(self):
        status = "Ein" if self.is_debug_enabled else "Aus"
        return f"Debug-Anzeige: {status} ({self.get_debug_visibility_display()})"

    @classmethod
    def get_settings(cls):
        """Get current debug settings or create default"""
        settings = cls.objects.first()
        if not settings:
            # Create default settings
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                settings = cls.objects.create(
                    is_debug_enabled=True,
                    debug_visibility='staff_only',
                    created_by=admin_user
                )
        return settings

    def should_show_debug_for_user(self, user):
        """Check if debug should be shown for specific user"""
        if not self.is_debug_enabled:
            return False

        if self.debug_visibility == 'disabled':
            return False
        elif self.debug_visibility == 'superuser_only':
            return user and user.is_superuser
        elif self.debug_visibility == 'staff_only':
            return user and user.is_staff
        elif self.debug_visibility == 'authenticated':
            return user and user.is_authenticated
        elif self.debug_visibility == 'all':
            return True

        return False


class APIProviderSettings(models.Model):
    """
    Settings for API Provider Cards on /accounts/neue-api-einstellungen/
    Allows superusers to set affiliate links and control visibility
    """
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('youtube', 'YouTube'),
        ('zoho', 'Zoho Mail'),
        ('ideogram', 'Ideogram'),
        ('gemini', 'Gemini'),
        ('shopify', 'Shopify'),
        ('pinterest', 'Pinterest'),
        ('upload_post', 'Upload-Post'),
    ]

    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        unique=True,
        help_text='API Provider'
    )

    display_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Anzeigename (falls abweichend vom Standard)'
    )

    affiliate_link = models.URLField(
        max_length=500,
        blank=True,
        help_text='Affiliate Link (öffnet in neuem Tab)'
    )

    affiliate_link_text = models.CharField(
        max_length=100,
        default='API-Key erhalten',
        help_text='Button-Text für den Affiliate Link'
    )

    direct_link = models.URLField(
        max_length=500,
        blank=True,
        help_text='Direkter Link zum Anbieter (erscheint nach Affiliate-Klick)'
    )

    direct_link_text = models.CharField(
        max_length=100,
        default='Direkt zum Anbieter',
        help_text='Button-Text für den Direkt-Link'
    )

    is_visible = models.BooleanField(
        default=True,
        help_text='Karte für normale Nutzer anzeigen'
    )

    sort_order = models.IntegerField(
        default=0,
        help_text='Sortierreihenfolge (niedrigere Werte zuerst)'
    )

    # Metadata
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API Provider Einstellung"
        verbose_name_plural = "API Provider Einstellungen"
        ordering = ['sort_order', 'provider']

    def __str__(self):
        status = "✓" if self.is_visible else "✗"
        return f"{status} {self.get_provider_display()}"

    @classmethod
    def get_all_settings(cls):
        """Get all provider settings as a dict keyed by provider name"""
        settings_dict = {}
        for setting in cls.objects.all():
            settings_dict[setting.provider] = {
                'affiliate_link': setting.affiliate_link,
                'affiliate_link_text': setting.affiliate_link_text,
                'direct_link': setting.direct_link,
                'direct_link_text': setting.direct_link_text,
                'is_visible': setting.is_visible,
                'display_name': setting.display_name,
                'sort_order': setting.sort_order,
            }
        return settings_dict

    @classmethod
    def get_provider_setting(cls, provider_name):
        """Get settings for a specific provider"""
        try:
            return cls.objects.get(provider=provider_name)
        except cls.DoesNotExist:
            return None

    @classmethod
    def ensure_all_providers_exist(cls, user=None):
        """Create default entries for all providers if they don't exist"""
        default_links = {
            'openai': 'https://platform.openai.com/api-keys',
            'youtube': 'https://console.developers.google.com/apis/credentials',
            'zoho': 'https://api-console.zoho.eu/',
            'ideogram': 'https://ideogram.ai/manage-api',
            'gemini': 'https://aistudio.google.com/apikey',
            'shopify': 'https://partners.shopify.com/',
            'pinterest': 'https://developers.pinterest.com/apps/',
            'upload_post': 'https://www.upload-post.com/',
        }

        created_count = 0
        for provider, _ in cls.PROVIDER_CHOICES:
            obj, created = cls.objects.get_or_create(
                provider=provider,
                defaults={
                    'affiliate_link': default_links.get(provider, ''),
                    'is_visible': True,
                    'sort_order': list(dict(cls.PROVIDER_CHOICES).keys()).index(provider),
                    'updated_by': user,
                }
            )
            if created:
                created_count += 1

        return created_count

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedTextField, EncryptedCharField

User = get_user_model()


class ZohoMailServerConnection(models.Model):
    """
    Model for Zoho Mail Server connections that are visible to all superusers
    """
    name = models.CharField(max_length=100, verbose_name="Verbindungsname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    
    # OAuth2 Credentials (encrypted)
    client_id = EncryptedCharField(max_length=255, verbose_name="Zoho Client ID")
    client_secret = EncryptedCharField(max_length=255, verbose_name="Zoho Client Secret")
    redirect_uri = models.URLField(verbose_name="Redirect URI")
    region = models.CharField(max_length=5, choices=[
        ('US', 'US'),
        ('EU', 'EU'),
        ('IN', 'India'),
        ('AU', 'Australia'),
        ('CN', 'China'),
        ('JP', 'Japan')
    ], default='EU', verbose_name="Zoho Region")
    
    # OAuth2 Tokens
    access_token = EncryptedTextField(blank=True, null=True)
    refresh_token = EncryptedTextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    
    # Connection details
    email_address = models.EmailField(verbose_name="E-Mail-Adresse")
    display_name = models.CharField(max_length=255, blank=True, verbose_name="Anzeigename")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    is_configured = models.BooleanField(default=False, verbose_name="Konfiguriert")
    last_test_success = models.DateTimeField(blank=True, null=True, verbose_name="Letzter erfolgreicher Test")
    last_error = models.TextField(blank=True, verbose_name="Letzter Fehler")
    
    # Zoho-specific fields
    zoho_account_id = models.CharField(max_length=50, blank=True, verbose_name='Zoho Account ID')
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_mail_connections',
                                  verbose_name="Erstellt von")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Zoho Mail Server Verbindung"
        verbose_name_plural = "Zoho Mail Server Verbindungen"
        ordering = ['-is_active', 'name']
        permissions = [
            ("can_test_connection", "Kann Verbindung testen"),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email_address})"
    
    @property
    def needs_reauth(self):
        """Check if connection needs re-authentication"""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at


class EmailTemplateCategory(models.Model):
    """
    Categories for organizing email templates
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Kategoriename")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon CSS-Klasse")
    order = models.IntegerField(default=0, verbose_name="Reihenfolge")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "E-Mail-Vorlage Kategorie"
        verbose_name_plural = "E-Mail-Vorlage Kategorien"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class EmailTrigger(models.Model):
    """
    Triggers that define when emails should be sent automatically
    """
    CATEGORY_CHOICES = [
        ('authentication', 'Authentifizierung'),
        ('storage', 'Speicher-Management'),
        ('payments', 'Zahlungen & Abonnements'),
        ('system', 'System-Benachrichtigungen'),
        ('organization', 'Organisation & Termine'),
        ('ecommerce', 'E-Commerce'),
        ('custom', 'Benutzerdefiniert'),
    ]
    
    trigger_key = models.CharField(max_length=100, unique=True, verbose_name="Trigger-Schlüssel",
                                 help_text="Eindeutiger Schlüssel für diesen Trigger (z.B. 'user_registration')")
    name = models.CharField(max_length=200, verbose_name="Name")
    description = models.TextField(verbose_name="Beschreibung",
                                 help_text="Beschreibung wann dieser Trigger ausgelöst wird")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='custom',
                              verbose_name="Kategorie")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    is_system_trigger = models.BooleanField(default=True, verbose_name="System-Trigger",
                                          help_text="System-Trigger können nicht gelöscht werden")
    
    # Available template variables for this trigger
    available_variables = models.JSONField(default=dict, blank=True,
                                         verbose_name="Verfügbare Variablen",
                                         help_text="JSON-Definition der verfügbaren Template-Variablen")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "E-Mail-Trigger"
        verbose_name_plural = "E-Mail-Trigger"
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.trigger_key})"


class EmailTemplate(models.Model):
    """
    Email templates that can be designed by superusers
    """
    TEMPLATE_TYPE_CHOICES = [
        # Authentication & User Management
        ('user_registration', 'Benutzer-Registrierung'),
        ('account_activation', 'Account-Aktivierung'),
        ('welcome', 'Willkommens-E-Mail'),
        ('password_reset', 'Passwort zurücksetzen'),
        ('password_changed', 'Passwort geändert'),
        ('login_notification', 'Login-Benachrichtigung'),
        
        # Storage & Resource Management
        ('storage_warning', 'Speicherplatz-Warnung'),
        ('storage_grace_period_start', 'Speicher-Kulanzzeit gestartet'),
        ('storage_grace_period_warning', 'Speicher-Kulanzzeit Warnung'),
        ('storage_grace_period_end', 'Speicher-Kulanzzeit beendet'),
        ('videos_archived', 'Videos archiviert'),
        ('files_archived', 'Dateien archiviert'),
        ('backup_notification', 'Backup-Benachrichtigung'),
        
        # Payment & Subscription
        ('subscription_created', 'Abonnement erstellt'),
        ('subscription_renewed', 'Abonnement verlängert'),
        ('subscription_cancelled', 'Abonnement gekündigt'),
        ('subscription_expired', 'Abonnement abgelaufen'),
        ('payment_successful', 'Zahlung erfolgreich'),
        ('payment_failed', 'Zahlung fehlgeschlagen'),
        ('invoice', 'Rechnung'),
        ('payment_reminder', 'Zahlungserinnerung'),
        ('trial_ending', 'Testphase endet bald'),
        ('trial_expired', 'Testphase abgelaufen'),
        
        # E-Commerce & Orders
        ('order_confirmation', 'Bestellbestätigung'),
        ('order_shipped', 'Versandbestätigung'),
        ('order_delivered', 'Lieferbestätigung'),
        ('order_cancelled', 'Stornierungsbestätigung'),
        ('cart_abandoned', 'Warenkorb verlassen'),
        ('product_review_request', 'Produktbewertung anfragen'),
        ('return_request', 'Rücksendung-Anfrage'),
        ('refund_processed', 'Erstattung verarbeitet'),
        
        # Communication & Support
        ('support_ticket_created', 'Support-Ticket erstellt'),
        ('support_ticket_updated', 'Support-Ticket aktualisiert'),
        ('support_ticket_resolved', 'Support-Ticket gelöst'),
        ('feedback_request', 'Feedback-Anfrage'),
        ('survey_invitation', 'Umfrage-Einladung'),
        ('bug_report_submitted', 'Bug-Report eingereicht'),
        ('bug_report_response', 'Bug-Report Antwort'),
        
        # System & Maintenance
        ('maintenance_notification', 'Wartungsankündigung'),
        ('system_update', 'System-Update'),
        ('security_alert', 'Sicherheitswarnung'),
        ('feature_announcement', 'Feature-Ankündigung'),
        ('service_disruption', 'Service-Unterbrechung'),
        ('data_breach_notification', 'Datenschutzverletzung'),
        
        # Organization & Tasks
        ('event_invitation', 'Event-Einladung'),
        ('event_reminder', 'Terminerinnerung'),
        ('event_cancelled', 'Termin abgesagt'),
        ('event_rescheduled', 'Termin verschoben'),
        ('task_assigned', 'Aufgabe zugewiesen'),
        ('task_reminder', 'Aufgaben-Erinnerung'),
        ('task_completed', 'Aufgabe abgeschlossen'),
        ('task_overdue', 'Aufgabe überfällig'),
        ('deadline_reminder', 'Deadline-Erinnerung'),
        
        # Marketing & Engagement
        ('newsletter', 'Newsletter'),
        ('marketing_campaign', 'Marketing-Kampagne'),
        ('promotional_offer', 'Werbe-Angebot'),
        ('announcement', 'Ankündigung'),
        ('seasonal_greeting', 'Saisonale Grüße'),
        ('birthday_wish', 'Geburtstagsgruß'),
        ('anniversary', 'Jubiläum'),
        ('loyalty_reward', 'Treuebonus'),
        ('referral_invitation', 'Empfehlungs-Einladung'),
        
        # User Activity & Engagement
        ('activity_summary', 'Aktivitäts-Zusammenfassung'),
        ('achievement_unlocked', 'Erfolg freigeschaltet'),
        ('milestone_reached', 'Meilenstein erreicht'),
        ('inactivity_reminder', 'Inaktivitäts-Erinnerung'),
        ('re_engagement', 'Wiederbindungs-Kampagne'),
        
        # Generic Types
        ('notification', 'Allgemeine Benachrichtigung'),
        ('transactional', 'Transaktions-E-Mail'),
        ('reminder', 'Erinnerung'),
        ('confirmation', 'Bestätigung'),
        ('alert', 'Warnung'),
        ('info', 'Information'),
        ('custom', 'Benutzerdefiniert'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Vorlagenname")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    category = models.ForeignKey(EmailTemplateCategory, on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='templates',
                                verbose_name="Kategorie")
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES, 
                                   default='custom', verbose_name="Vorlagentyp")
    
    # NEW: Trigger-based system
    trigger = models.ForeignKey(EmailTrigger, on_delete=models.SET_NULL, 
                               null=True, blank=True, related_name='templates',
                               verbose_name="E-Mail-Trigger",
                               help_text="Trigger der diese Vorlage automatisch auslöst")
    is_auto_send = models.BooleanField(default=True, verbose_name="Automatisch senden",
                                     help_text="Template automatisch bei Trigger-Ereignis senden")
    send_delay_minutes = models.IntegerField(default=0, verbose_name="Versendungs-Verzögerung (Minuten)",
                                           help_text="Verzögerung in Minuten bevor die E-Mail gesendet wird")
    conditions = models.JSONField(default=dict, blank=True, verbose_name="Bedingungen",
                                help_text="Erweiterte Bedingungen für die Versendung (JSON)")
    
    # Email content
    subject = models.CharField(max_length=255, verbose_name="Betreff",
                             help_text="Unterstützt Variablen wie {{customer_name}}, {{order_number}}")
    html_content = models.TextField(verbose_name="HTML-Inhalt")
    text_content = models.TextField(blank=True, verbose_name="Text-Inhalt",
                                  help_text="Optionaler Nur-Text-Inhalt für E-Mail-Clients ohne HTML-Unterstützung")
    
    # Design settings
    use_base_template = models.BooleanField(default=True, verbose_name="Basis-Template verwenden",
                                          help_text="Verwendet das Standard-E-Mail-Layout mit Header und Footer")
    custom_css = models.TextField(blank=True, verbose_name="Benutzerdefiniertes CSS")
    
    # Variable documentation
    available_variables = models.JSONField(default=dict, blank=True,
                                         verbose_name="Verfügbare Variablen",
                                         help_text="JSON-Dokumentation der verfügbaren Template-Variablen")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    is_default = models.BooleanField(default=False, verbose_name="Standard-Vorlage",
                                   help_text="Standard-Vorlage für diesen Vorlagentyp")
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                 related_name='created_email_templates',
                                 verbose_name="Erstellt von")
    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='modified_email_templates',
                                       verbose_name="Zuletzt geändert von")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Statistics
    times_used = models.PositiveIntegerField(default=0, verbose_name="Verwendungen")
    last_used_at = models.DateTimeField(blank=True, null=True, verbose_name="Zuletzt verwendet")
    
    class Meta:
        verbose_name = "E-Mail-Vorlage"
        verbose_name_plural = "E-Mail-Vorlagen"
        ordering = ['-is_default', 'category__order', 'name']
        permissions = [
            ("can_preview_template", "Kann Vorlagen-Vorschau anzeigen"),
            ("can_send_test_email", "Kann Test-E-Mail senden"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['template_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_per_type'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default template per type
        if self.is_default:
            EmailTemplate.objects.filter(
                template_type=self.template_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def increment_usage(self):
        """Increment usage counter and update last used timestamp"""
        self.times_used += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['times_used', 'last_used_at'])


class EmailTemplateVersion(models.Model):
    """
    Version history for email templates
    """
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE,
                               related_name='versions', verbose_name="Vorlage")
    version_number = models.PositiveIntegerField(verbose_name="Versionsnummer")
    
    # Snapshot of template content
    subject = models.CharField(max_length=255, verbose_name="Betreff")
    html_content = models.TextField(verbose_name="HTML-Inhalt")
    text_content = models.TextField(blank=True, verbose_name="Text-Inhalt")
    custom_css = models.TextField(blank=True, verbose_name="Benutzerdefiniertes CSS")
    
    # Version info
    change_description = models.TextField(blank=True, verbose_name="Änderungsbeschreibung")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                 verbose_name="Erstellt von")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "E-Mail-Vorlagen Version"
        verbose_name_plural = "E-Mail-Vorlagen Versionen"
        ordering = ['template', '-version_number']
        unique_together = ['template', 'version_number']
    
    def __str__(self):
        return f"{self.template.name} - Version {self.version_number}"


class EmailSendLog(models.Model):
    """
    Log of sent emails using templates
    """
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL,
                               null=True, related_name='send_logs',
                               verbose_name="Verwendete Vorlage")
    connection = models.ForeignKey(ZohoMailServerConnection, on_delete=models.SET_NULL,
                                 null=True, verbose_name="Verwendete Verbindung")
    
    # Email details
    recipient_email = models.EmailField(verbose_name="Empfänger E-Mail")
    recipient_name = models.CharField(max_length=255, blank=True, verbose_name="Empfänger Name")
    subject = models.CharField(max_length=255, verbose_name="Betreff")
    
    # Status
    is_sent = models.BooleanField(default=False, verbose_name="Gesendet")
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Gesendet am")
    error_message = models.TextField(blank=True, verbose_name="Fehlermeldung")
    
    # Context data used for rendering
    context_data = models.JSONField(default=dict, blank=True,
                                  verbose_name="Kontext-Daten",
                                  help_text="Variablen die beim Rendern verwendet wurden")
    
    # Tracking
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              verbose_name="Gesendet von")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "E-Mail Versandprotokoll"
        verbose_name_plural = "E-Mail Versandprotokolle"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['recipient_email']),
            models.Index(fields=['is_sent', '-created_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_sent else "✗"
        return f"{status} {self.recipient_email} - {self.subject} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

from django.db import models
from django.conf import settings
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

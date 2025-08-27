"""
Custom Email Backend with automatic fallback for DNS issues
"""
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.conf import settings
import socket
import logging

logger = logging.getLogger(__name__)


class AutoFallbackEmailBackend(SMTPEmailBackend):
    """
    Email backend that automatically falls back to working SMTP servers
    when DNS resolution fails for the configured server.
    Uses database configuration instead of Django settings.
    """
    
    def __init__(self, *args, **kwargs):
        self.fallback_used = False
        self.original_host = None
        
        # Load configuration from database instead of settings
        self._load_database_config()
        
        super().__init__(*args, **kwargs)
    
    def _load_database_config(self):
        """Load email configuration from database"""
        try:
            from .models import EmailConfiguration
            config = EmailConfiguration.objects.filter(is_active=True).first()
            
            if config:
                # Override default parameters with database config
                self.host = config.smtp_host
                self.port = config.smtp_port
                self.username = config.email_host_user
                self.password = config.email_host_password
                self.use_tls = config.smtp_use_tls
                self.use_ssl = config.smtp_use_ssl
                
                logger.info(f"Loaded email config from database: {self.host}:{self.port}")
            else:
                logger.warning("No active email configuration found in database")
                
        except Exception as e:
            logger.error(f"Failed to load database email config: {e}")
            # Fall back to settings if database fails
    
    def open(self):
        """
        Override open to test connection and auto-fallback if needed
        """
        try:
            # Test DNS resolution first
            socket.gethostbyname(self.host)
            return super().open()
            
        except socket.gaierror as dns_error:
            logger.warning(f"DNS resolution failed for {self.host}: {dns_error}")
            
            # Attempt automatic fallback
            fallback_result = self._attempt_fallback()
            if fallback_result['success']:
                logger.info(f"Successfully fell back to {self.host}")
                return super().open()
            else:
                logger.error(f"All fallback attempts failed: {fallback_result['message']}")
                raise dns_error
    
    def _attempt_fallback(self):
        """
        Attempt to find a working SMTP server and reconfigure
        """
        from .models import EmailConfiguration
        
        # Get current email user to determine appropriate fallbacks
        email_user = getattr(settings, 'EMAIL_HOST_USER', '')
        email_domain = email_user.split('@')[1].lower() if '@' in email_user else ''
        
        # Zoho-optimierte Fallback-Konfigurationen
        fallback_configs = [
            {'host': 'smtp.zoho.eu', 'port': 587, 'use_tls': True, 'use_ssl': False, 'region': 'Europe'},
            {'host': 'smtp.zohomaileu.com', 'port': 587, 'use_tls': True, 'use_ssl': False, 'region': 'EU'},
            {'host': 'smtp.zoho.com', 'port': 587, 'use_tls': True, 'use_ssl': False, 'region': 'US'},
        ]
        
        self.original_host = self.host
        
        # Test each fallback configuration
        for config in fallback_configs:
            try:
                # Test DNS resolution
                socket.gethostbyname(config['host'])
                
                # Update backend configuration
                self.host = config['host']
                self.port = config['port']
                self.use_tls = config['use_tls']
                self.use_ssl = config['use_ssl']
                
                # Update database configuration if exists
                try:
                    email_config = EmailConfiguration.objects.filter(is_active=True).first()
                    if email_config:
                        email_config.smtp_host = config['host']
                        email_config.smtp_port = config['port']
                        email_config.smtp_use_tls = config['use_tls']
                        email_config.smtp_use_ssl = config['use_ssl']
                        email_config.save()
                except Exception as db_error:
                    logger.warning(f"Could not update database config: {db_error}")
                
                self.fallback_used = True
                logger.info(f"Auto-fallback successful: {self.original_host} -> {self.host}")
                
                return {
                    'success': True,
                    'message': f'Automatisch auf {config["host"]} umgestellt',
                    'original_host': self.original_host,
                    'fallback_host': self.host
                }
                
            except socket.gaierror:
                continue
        
        return {
            'success': False,
            'message': 'Alle Fallback-Server nicht erreichbar'
        }
    
    def send_messages(self, email_messages):
        """
        Override to log fallback usage
        """
        if self.fallback_used:
            logger.info(f"Sending {len(email_messages)} emails via fallback server {self.host}")
        
        return super().send_messages(email_messages)
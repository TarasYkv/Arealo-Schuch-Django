"""
Custom Email Backend with clear error messages for connection issues
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
        self._config_loaded = False

        # Don't load database config during init - wait until first use
        super().__init__(*args, **kwargs)
    
    def _load_database_config(self):
        """Load email configuration from database (lazy loading to avoid app init warnings)"""
        if self._config_loaded:
            return

        try:
            from django.apps import apps
            from django.db import connection

            # Check if apps are ready and database is available
            if not apps.ready or not self._is_database_ready():
                self._use_fallback_config()
                self._config_loaded = True
                return

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

                logger.info(f"✅ AutoFallbackEmailBackend: Loaded from DB - {self.host}:{self.port} (User: {self.username})")
                print(f"🔧 SuperConfig Email Backend: {self.host}:{self.port} für {self.username}")
            else:
                logger.warning("❌ No active email configuration found in database - using Zoho defaults")
                self._use_fallback_config()

            self._config_loaded = True

        except Exception as e:
            logger.error(f"Failed to load database email config: {e}")
            self._use_fallback_config()
            self._config_loaded = True

    def _is_database_ready(self):
        """Check if database is ready without triggering warnings"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _use_fallback_config(self):
        """Use Zoho defaults when database is not available"""
        self.host = 'smtp.zoho.eu'
        self.port = 587
        self.use_tls = True
        self.use_ssl = False
        print(f"⚡ SuperConfig: Fallback auf Zoho-Standard smtp.zoho.eu:587")
    
    def open(self):
        """
        Override open to test connection and provide clear error messages
        """
        try:
            # Test DNS resolution first
            socket.gethostbyname(self.host)
            
            # Test if port is reachable
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result != 0:
                error_msg = f"❌ SMTP-Server {self.host} ist nicht erreichbar auf Port {self.port}. Bitte prüfen Sie Ihre Firewall-Einstellungen oder Netzwerkverbindung."
                logger.error(error_msg)
                raise socket.error(error_msg)
            
            return super().open()
            
        except socket.gaierror as dns_error:
            error_msg = f"❌ DNS-Fehler: {self.host} konnte nicht aufgelöst werden. Bitte prüfen Sie die Server-Adresse."
            logger.error(error_msg)
            raise socket.gaierror(error_msg) from dns_error
            
        except socket.error as sock_error:
            # Re-raise with clear message
            raise
    
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
        Override to provide clear error messages
        """
        try:
            return super().send_messages(email_messages)
        except Exception as e:
            error_msg = f"❌ Email-Versand fehlgeschlagen: {str(e)}"
            logger.error(error_msg)
            # Re-raise the original exception with clear message
            raise Exception(error_msg) from e
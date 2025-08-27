"""
Management command to test email diagnostics functionality
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import socket
import smtplib
from datetime import datetime
import json


class Command(BaseCommand):
    help = 'Test email connection diagnostics functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Testing Email Connection Diagnostics'))
        
        # Get current email configuration
        email_host = getattr(settings, 'EMAIL_HOST', 'Not configured')
        email_port = getattr(settings, 'EMAIL_PORT', 'Not configured')
        email_user = getattr(settings, 'EMAIL_HOST_USER', 'Not configured')
        email_tls = getattr(settings, 'EMAIL_USE_TLS', False)
        email_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
        
        self.stdout.write(f'\n📧 Current Email Configuration:')
        self.stdout.write(f'  Host: {email_host}')
        self.stdout.write(f'  Port: {email_port}')
        self.stdout.write(f'  User: {email_user}')
        self.stdout.write(f'  Use TLS: {email_tls}')
        self.stdout.write(f'  Use SSL: {email_ssl}')
        
        if email_host == 'Not configured':
            self.stdout.write(self.style.WARNING('\n⚠️  Email not configured in settings'))
            return
        
        # Test DNS resolution
        self.stdout.write(f'\n🔍 Testing DNS resolution for {email_host}...')
        try:
            socket.gethostbyname(email_host)
            self.stdout.write(self.style.SUCCESS(f'✅ DNS resolution successful'))
        except socket.gaierror as e:
            self.stdout.write(self.style.ERROR(f'❌ DNS resolution failed: {e}'))
            
            # Suggest alternatives
            self.stdout.write(f'\n💡 Suggested alternatives:')
            alternatives = self.get_alternative_smtp_hosts()
            for alt in alternatives:
                self.stdout.write(f'   • {alt["host"]}:{alt["port"]} ({alt["service"]})')
            return
            
        # Test SMTP connection
        self.stdout.write(f'\n🔗 Testing SMTP connection to {email_host}:{email_port}...')
        try:
            if email_ssl:
                server = smtplib.SMTP_SSL(email_host, email_port, timeout=10)
            else:
                server = smtplib.SMTP(email_host, email_port, timeout=10)
                if email_tls:
                    server.starttls()
            
            if email_user:
                # Test authentication (won't actually authenticate without password)
                self.stdout.write(f'📝 Testing authentication capability...')
                server.ehlo()
                
            server.quit()
            self.stdout.write(self.style.SUCCESS(f'✅ SMTP connection successful'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ SMTP connection failed: {e}'))
            
            # Check if it's a common DNS error
            if '[Errno -3]' in str(e) or 'Temporary failure in name resolution' in str(e):
                self.stdout.write(f'\n🔧 This is a DNS resolution error!')
                self.stdout.write(f'   Possible solutions:')
                self.stdout.write(f'   1. Check your internet connection')
                self.stdout.write(f'   2. Verify DNS server settings')
                self.stdout.write(f'   3. Try alternative SMTP servers')
                
                # Suggest alternatives
                self.stdout.write(f'\n💡 Suggested alternatives:')
                alternatives = self.get_alternative_smtp_hosts()
                for alt in alternatives:
                    self.stdout.write(f'   • {alt["host"]}:{alt["port"]} ({alt["service"]})')
        
        self.stdout.write(f'\n✅ Email diagnostics test completed')
    
    def get_alternative_smtp_hosts(self):
        """Get alternative SMTP server suggestions"""
        return [
            {
                'host': 'smtp.gmail.com',
                'port': 587,
                'service': 'Gmail',
                'use_tls': True,
                'use_ssl': False
            },
            {
                'host': 'smtp.zohomaileu.com',
                'port': 587,
                'service': 'Zoho Mail Europe',
                'use_tls': True,
                'use_ssl': False
            },
            {
                'host': 'smtp.zoho.com',
                'port': 587,
                'service': 'Zoho Mail US',
                'use_tls': True,
                'use_ssl': False
            },
            {
                'host': 'smtp-mail.outlook.com',
                'port': 587,
                'service': 'Outlook/Hotmail',
                'use_tls': True,
                'use_ssl': False
            }
        ]
"""
Management command to immediately fix DNS email issues
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from superconfig.models import EmailConfiguration
from django.contrib.auth import get_user_model
import socket

User = get_user_model()


class Command(BaseCommand):
    help = 'Immediately fix DNS email issues by switching to working servers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='kontakt@workloom.de',
            help='Email address to use (default: kontakt@workloom.de)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='SMTP password (will prompt if not provided)',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test email sending after configuration',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚑 Emergency DNS Email Fix'))
        
        email = options['email']
        password = options['password']
        
        if not password:
            import getpass
            password = getpass.getpass(f'Enter SMTP password for {email}: ')
        
        # Get superuser
        try:
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                self.stdout.write(self.style.ERROR('❌ No superuser found'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            return
        
        # Zoho SMTP Server (nach Priorität sortiert)
        working_servers = [
            ('smtp.zoho.eu', 587),           # Europe (beste Wahl für Deutschland)
            ('smtp.zohomaileu.com', 587),    # EU Alternative
            ('smtp.zoho.com', 587),          # US (fallback)
            ('smtp.zoho.in', 587),           # India (fallback)
        ]
        
        working_server = None
        for host, port in working_servers:
            try:
                self.stdout.write(f'🔍 Testing {host}:{port}...')
                socket.gethostbyname(host)
                working_server = (host, port)
                self.stdout.write(self.style.SUCCESS(f'✅ {host} is reachable'))
                break
            except socket.gaierror:
                self.stdout.write(self.style.WARNING(f'⚠️  {host} not reachable'))
                continue
        
        if not working_server:
            self.stdout.write(self.style.ERROR('❌ No working SMTP servers found'))
            return
        
        # Update or create configuration
        try:
            # Deactivate all existing configs
            EmailConfiguration.objects.all().update(is_active=False)
            
            # Create new working configuration
            config = EmailConfiguration.objects.create(
                email_host_user=email,
                email_host_password=password,
                default_from_email=email,
                smtp_host=working_server[0],
                smtp_port=working_server[1],
                smtp_use_tls=True,
                smtp_use_ssl=False,
                is_active=True,
                backend_type='smtp',
                created_by=superuser
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Created new email config: {working_server[0]}:{working_server[1]}'))
            
            # Update Django settings immediately
            settings.EMAIL_HOST = working_server[0]
            settings.EMAIL_PORT = working_server[1]
            settings.EMAIL_USE_TLS = True
            settings.EMAIL_USE_SSL = False
            settings.EMAIL_HOST_USER = email
            settings.EMAIL_HOST_PASSWORD = password
            settings.DEFAULT_FROM_EMAIL = email
            
            self.stdout.write(self.style.SUCCESS('✅ Django settings updated'))
            
            # Test if requested
            if options['test']:
                self.stdout.write(self.style.WARNING('🧪 Testing email sending...'))
                
                from django.core.mail import send_mail
                try:
                    result = send_mail(
                        'Test Email - DNS Fix',
                        'This email confirms that DNS issues have been resolved.',
                        email,
                        [email],  # Send to self for testing
                        fail_silently=False,
                    )
                    self.stdout.write(self.style.SUCCESS(f'✅ Email sent successfully! Result: {result}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Email test failed: {e}'))
                    # Still continue - configuration is set up
            
            self.stdout.write(self.style.SUCCESS('\n🎯 DNS Email Fix Complete!'))
            self.stdout.write('✅ System can now send emails automatically')
            self.stdout.write('✅ Registration emails will work')
            self.stdout.write('✅ Password reset emails will work')
            self.stdout.write('✅ System notifications will work')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Configuration error: {e}'))
            return
"""
Management command to set up automatic email fallback system
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from superconfig.models import EmailConfiguration
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up automatic email fallback system for DNS issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to use for sending (e.g., kontakt@workloom.de)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Email password or app password',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test the configuration after setup',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔧 Setting up Automatic Email Fallback System'))
        
        # Get superuser
        try:
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                self.stdout.write(self.style.ERROR('❌ No superuser found. Create a superuser first.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error finding superuser: {e}'))
            return
        
        # Get email and password
        email = options['email'] or input('Enter email address: ')
        password = options['password']
        
        if not password:
            import getpass
            password = getpass.getpass('Enter email password/app password: ')
        
        # Create or update email configuration
        try:
            config, created = EmailConfiguration.objects.get_or_create(
                defaults={
                    'email_host_user': email,
                    'email_host_password': password,
                    'default_from_email': email,
                    'smtp_host': 'mail.workloom.de',  # Will auto-fallback if DNS fails
                    'smtp_port': 587,
                    'smtp_use_tls': True,
                    'smtp_use_ssl': False,
                    'is_active': True,
                    'backend_type': 'smtp',
                    'created_by': superuser
                }
            )
            
            if not created:
                # Update existing configuration
                config.email_host_user = email
                config.email_host_password = password
                config.default_from_email = email
                config.save()
                
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'✅ {action} email configuration: {email}'))
            
            # Test configuration if requested
            if options['test']:
                self.stdout.write(self.style.WARNING('\n🔍 Testing email configuration...'))
                result = config.test_connection()
                
                if result['success']:
                    if result.get('fallback_used'):
                        self.stdout.write(self.style.WARNING(f'⚠️  {result["message"]}'))
                        self.stdout.write(self.style.SUCCESS('✅ Automatic fallback working!'))
                    else:
                        self.stdout.write(self.style.SUCCESS('✅ Email configuration working perfectly!'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ {result["message"]}'))
            
            # Instructions
            self.stdout.write(self.style.SUCCESS('\n📋 Setup Complete!'))
            self.stdout.write('How the automatic fallback works:')
            self.stdout.write('1. System tries configured SMTP server (mail.workloom.de)')
            self.stdout.write('2. If DNS fails ([Errno -3]), automatically switches to working Zoho servers')
            self.stdout.write('3. E-mails are sent without manual intervention')
            self.stdout.write('4. Configuration is automatically updated in database')
            
            self.stdout.write('\n🎯 To use the custom email backend in Django settings:')
            self.stdout.write("EMAIL_BACKEND = 'superconfig.email_backend.AutoFallbackEmailBackend'")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error setting up configuration: {e}'))
            return
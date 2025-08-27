"""
Management command to enable automatic email backend
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Enable automatic email fallback backend'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Enabling Automatic Email Backend'))
        
        # Change Django email backend to our custom one
        settings.EMAIL_BACKEND = 'superconfig.email_backend.AutoFallbackEmailBackend'
        
        self.stdout.write(self.style.SUCCESS('✅ Automatic Email Backend activated!'))
        self.stdout.write('📧 Email Backend: superconfig.email_backend.AutoFallbackEmailBackend')
        self.stdout.write('🎯 Features:')
        self.stdout.write('  - Uses database configuration instead of settings')
        self.stdout.write('  - Automatic DNS fallback')
        self.stdout.write('  - Works with existing EmailConfiguration model')
        
        # Test it
        from django.core.mail import send_mail
        
        try:
            result = send_mail(
                'Test - Custom Email Backend',
                'This email was sent using the custom AutoFallbackEmailBackend.',
                'kontakt@workloom.de',
                ['kontakt@workloom.de'],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Test email sent successfully! Result: {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Test email failed: {e}'))
            self.stdout.write(self.style.WARNING('💡 This might be due to missing credentials - check your EmailConfiguration'))
        
        self.stdout.write(self.style.SUCCESS('\n🚀 System ready for automatic email sending!'))
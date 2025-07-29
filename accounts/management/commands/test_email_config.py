from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Testet die E-Mail-Konfiguration und sendet eine Test-E-Mail'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='E-Mail-Adresse für Test-E-Mail',
            default='test@example.com'
        )
        parser.add_argument(
            '--send-test',
            action='store_true',
            help='Sendet eine Test-E-Mail',
        )

    def handle(self, *args, **options):
        self.stdout.write('🔧 E-Mail-Konfiguration wird überprüft...\n')
        
        # Prüfe Konfiguration
        self.stdout.write('📋 Aktuelle Konfiguration:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'  EMAIL_HOST_PASSWORD: {"***" if settings.EMAIL_HOST_PASSWORD else "NICHT GESETZT"}')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write()
        
        # Prüfe Environment-Variablen
        self.stdout.write('🌍 Environment-Variablen:')
        env_vars = ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL']
        missing_vars = []
        
        for var in env_vars:
            value = os.getenv(var)
            if var == 'EMAIL_HOST_PASSWORD':
                display_value = "***" if value else "NICHT GESETZT"
            else:
                display_value = value or "NICHT GESETZT"
            
            self.stdout.write(f'  {var}: {display_value}')
            
            if not value and var in ['EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']:
                missing_vars.append(var)
        
        self.stdout.write()
        
        # Prüfe ob E-Mails versendet werden können
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.stdout.write(self.style.WARNING(
                '⚠️  WARNUNG: E-Mail-Backend ist auf Console eingestellt.\n'
                '   E-Mails werden nur in der Konsole ausgegeben, nicht tatsächlich versendet.'
            ))
        elif missing_vars:
            self.stdout.write(self.style.ERROR(
                f'❌ FEHLER: Fehlende E-Mail-Credentials: {", ".join(missing_vars)}'
            ))
            self.stdout.write('\n💡 So beheben Sie das Problem:')
            self.stdout.write('1. Öffnen Sie die .env Datei im Projekt-Root')
            self.stdout.write('2. Setzen Sie die folgenden Werte:')
            self.stdout.write('   EMAIL_HOST_USER=ihre-email@domain.com')
            self.stdout.write('   EMAIL_HOST_PASSWORD=ihr-app-passwort')
            self.stdout.write('\n📧 Für Gmail:')
            self.stdout.write('   - Aktivieren Sie 2-Faktor-Authentifizierung')
            self.stdout.write('   - Generieren Sie ein App-Passwort')
            self.stdout.write('   - Verwenden Sie das App-Passwort, nicht Ihr normales Passwort')
        else:
            self.stdout.write(self.style.SUCCESS('✅ E-Mail-Konfiguration sieht vollständig aus!'))
            
            if options['send_test']:
                self.send_test_email(options['to'])
    
    def send_test_email(self, to_email):
        self.stdout.write(f'\n📤 Sende Test-E-Mail an {to_email}...')
        
        try:
            send_mail(
                subject='Workloom E-Mail Test',
                message='Dies ist eine Test-E-Mail von Workloom.\n\n'
                       'Wenn Sie diese E-Mail erhalten haben, '
                       'funktioniert die E-Mail-Konfiguration korrekt!',
                from_email=None,  # Verwendet DEFAULT_FROM_EMAIL
                recipient_list=[to_email],
                html_message='''
                <h2>🎉 Workloom E-Mail Test</h2>
                <p>Dies ist eine Test-E-Mail von Workloom.</p>
                <p><strong>Wenn Sie diese E-Mail erhalten haben, 
                funktioniert die E-Mail-Konfiguration korrekt!</strong></p>
                <hr>
                <p><small>© 2025 Workloom - Ihre All-in-One Arbeitsplattform</small></p>
                '''
            )
            self.stdout.write(self.style.SUCCESS('✅ Test-E-Mail wurde erfolgreich gesendet!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Fehler beim Senden der Test-E-Mail: {str(e)}'))
            self.stdout.write('\n🔍 Mögliche Ursachen:')
            self.stdout.write('   - Falsche E-Mail-Credentials')
            self.stdout.write('   - SMTP-Server nicht erreichbar')
            self.stdout.write('   - App-Passwort erforderlich (bei Gmail)')
            self.stdout.write('   - Firewall blockiert SMTP-Port 587')
"""
Management Command zum Testen von E-Mail-Vorlagen

Verwendung:
    python manage.py test_email_templates --email your@email.com
    python manage.py test_email_templates --email your@email.com --template 8
    python manage.py test_email_templates --email your@email.com --trigger user_registration
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template import Template, Context
from email_templates.models import EmailTemplate, EmailTrigger
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Testet E-Mail-Vorlagen durch Versand an eine Test-E-Mail-Adresse'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='E-Mail-Adresse für Test-Versand'
        )
        parser.add_argument(
            '--template',
            type=int,
            help='ID einer spezifischen Vorlage zum Testen'
        )
        parser.add_argument(
            '--trigger',
            type=str,
            help='Trigger-Key einer spezifischen Vorlage zum Testen'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Alle aktiven Vorlagen testen'
        )

    def handle(self, *args, **options):
        test_email = options['email']

        self.stdout.write(self.style.SUCCESS(f'\n📧 E-Mail-Vorlagen Tester'))
        self.stdout.write(self.style.SUCCESS(f'📨 Test-E-Mails gehen an: {test_email}\n'))

        # Test-Daten für Variablen
        test_context = {
            'user_name': 'Max Mustermann',
            'user_email': test_email,
            'kunde_name': 'Max Mustermann',
            'kunde_email': test_email,
            'confirmation_link': 'https://example.com/confirm/test-token-123',
            'reset_link': 'https://example.com/reset/test-token-456',
            'bestellnummer': 'TEST-12345',
            'datum': '01.10.2025',
            'betrag': '99,99 €',
            'support_email': 'support@workloom.de',
            'company_address': 'Workloom GmbH, Musterstraße 123, 12345 Musterstadt',
            'unread_count': 5,
            'storage_used': '8.5 GB',
            'storage_limit': '10 GB',
            'storage_percent': '85%',
            'grace_period_days': 7,
            'upgrade_url': 'https://example.com/upgrade',
            'plan_name': 'Pro Plan',
            'plan_price': '29,99 €',
        }

        # Wähle Vorlagen basierend auf Argumenten
        if options.get('template'):
            templates = EmailTemplate.objects.filter(id=options['template'])
            if not templates.exists():
                self.stdout.write(self.style.ERROR(f'❌ Template mit ID {options["template"]} nicht gefunden'))
                return
        elif options.get('trigger'):
            try:
                trigger = EmailTrigger.objects.get(trigger_key=options['trigger'])
                templates = EmailTemplate.objects.filter(trigger=trigger, is_active=True)
                if not templates.exists():
                    self.stdout.write(self.style.ERROR(f'❌ Keine aktiven Templates für Trigger "{options["trigger"]}" gefunden'))
                    return
            except EmailTrigger.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Trigger "{options["trigger"]}" nicht gefunden'))
                return
        elif options.get('all'):
            templates = EmailTemplate.objects.filter(is_active=True)
        else:
            # Zeige Liste zum manuellen Auswählen
            self.show_template_list()
            return

        # Teste alle gewählten Vorlagen
        success_count = 0
        error_count = 0

        for template in templates:
            try:
                self.stdout.write(f'\n📧 Teste: {template.name}')

                # Rendere Subject
                subject_template = Template(template.subject)
                subject = subject_template.render(Context(test_context))

                # Rendere HTML Content
                html_template = Template(template.html_content)
                html_content = html_template.render(Context(test_context))

                # Rendere Text Content (optional)
                text_content = template.text_content
                if text_content:
                    text_template = Template(text_content)
                    text_content = text_template.render(Context(test_context))

                # Versende E-Mail
                from django.core.mail import EmailMultiAlternatives

                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content or 'Dies ist eine Test-E-Mail.',
                    from_email=None,  # Verwendet DEFAULT_FROM_EMAIL
                    to=[test_email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()

                self.stdout.write(self.style.SUCCESS(f'  ✅ Erfolgreich versendet!'))
                self.stdout.write(f'  📝 Subject: {subject}')
                if template.trigger:
                    self.stdout.write(f'  🔔 Trigger: {template.trigger.name}')

                success_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Fehler: {str(e)}'))
                error_count += 1

        # Zusammenfassung
        self.stdout.write(self.style.SUCCESS(f'\n\n📊 Zusammenfassung:'))
        self.stdout.write(self.style.SUCCESS(f'  ✅ Erfolgreich: {success_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'  ❌ Fehler: {error_count}'))
        self.stdout.write(self.style.SUCCESS(f'\n📬 Prüfen Sie Ihr E-Mail-Postfach: {test_email}\n'))

    def show_template_list(self):
        """Zeigt eine Liste aller verfügbaren Templates"""
        self.stdout.write(self.style.SUCCESS('\n📋 Verfügbare E-Mail-Vorlagen:\n'))

        templates = EmailTemplate.objects.filter(is_active=True).order_by('trigger__name', 'name')

        current_trigger = None
        for template in templates:
            if template.trigger != current_trigger:
                current_trigger = template.trigger
                if current_trigger:
                    self.stdout.write(self.style.SUCCESS(f'\n🔔 {current_trigger.name}:'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'\n📧 Ohne Trigger:'))

            self.stdout.write(f'  • ID {template.id}: {template.name}')

        self.stdout.write(self.style.WARNING('\n💡 Verwendung:'))
        self.stdout.write('  python manage.py test_email_templates --email your@email.com --template 8')
        self.stdout.write('  python manage.py test_email_templates --email your@email.com --trigger user_registration')
        self.stdout.write('  python manage.py test_email_templates --email your@email.com --all')
        self.stdout.write('')

from django.core.management.base import BaseCommand
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Aktualisiert bestehende Benutzer für E-Mail-Verifikation System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verify-all',
            action='store_true',
            help='Markiert alle bestehenden Benutzer als E-Mail-verifiziert',
        )
        parser.add_argument(
            '--activate-all',
            action='store_true',
            help='Aktiviert alle bestehenden Benutzer',
        )

    def handle(self, *args, **options):
        if options['verify_all']:
            updated = CustomUser.objects.filter(email_verified=False).update(
                email_verified=True
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ {updated} Benutzer als E-Mail-verifiziert markiert.')
            )

        if options['activate_all']:
            activated = CustomUser.objects.filter(is_active=False).update(
                is_active=True
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ {activated} Benutzer aktiviert.')
            )
        
        # Status-Report
        total_users = CustomUser.objects.count()
        verified_users = CustomUser.objects.filter(email_verified=True).count()
        active_users = CustomUser.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\n📊 Status-Report:')
        self.stdout.write(f'Gesamte Benutzer: {total_users}')
        self.stdout.write(f'E-Mail-verifiziert: {verified_users}')
        self.stdout.write(f'Aktive Benutzer: {active_users}')
        
        if not options['verify_all'] and not options['activate_all']:
            self.stdout.write(f'\n💡 Verwenden Sie --verify-all oder --activate-all um bestehende Benutzer zu aktualisieren.')
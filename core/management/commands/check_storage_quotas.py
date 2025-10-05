"""
Management Command: Check Storage Quotas
=========================================
Prüft alle User auf Speicher-Überschreitungen und sendet Benachrichtigungen

Usage:
    python manage.py check_storage_quotas

Cron (täglich um 9 Uhr):
    0 9 * * * cd /path/to/project && python manage.py check_storage_quotas
"""

from django.core.management.base import BaseCommand
from core.storage_notifications import StorageNotificationService


class Command(BaseCommand):
    help = 'Prüft Speicher-Quotas aller Benutzer und sendet Benachrichtigungen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt welche Benachrichtigungen gesendet würden, ohne sie tatsächlich zu senden',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.MIGRATE_HEADING('Storage Quota Check'))
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - Keine E-Mails werden gesendet'))
            self.stdout.write('')

        try:
            if dry_run:
                # TODO: Implement dry-run logic
                self.stdout.write(self.style.WARNING('Dry-run Modus noch nicht implementiert'))
                result = {'total_checked': 0, 'users_notified': 0, 'usernames': []}
            else:
                result = StorageNotificationService.check_and_notify_all_users()

            # Ausgabe
            self.stdout.write(self.style.SUCCESS(f'✓ Geprüfte Benutzer: {result["total_checked"]}'))
            self.stdout.write(self.style.SUCCESS(f'✓ Benachrichtigungen gesendet: {result["users_notified"]}'))

            if result['usernames']:
                self.stdout.write('')
                self.stdout.write('Benachrichtigte Benutzer:')
                for username in result['usernames']:
                    self.stdout.write(f'  - {username}')

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ Storage Quota Check abgeschlossen!'))

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f'✗ Fehler: {str(e)}'))
            raise

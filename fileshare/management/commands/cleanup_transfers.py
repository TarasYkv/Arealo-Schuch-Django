from django.core.management.base import BaseCommand
from django.utils import timezone
from fileshare.models import Transfer
from fileshare.utils import clean_expired_transfers

class Command(BaseCommand):
    help = 'Bereinige abgelaufene Transfers und lösche ihre Dateien'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ausführen ohne tatsächlich Dateien zu löschen',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('TESTLAUF-MODUS - Keine Dateien werden gelöscht'))

        # Hole abgelaufene Transfers
        expired_transfers = Transfer.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )

        count = expired_transfers.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Keine abgelaufenen Transfers zum Bereinigen'))
            return

        self.stdout.write(f'{count} abgelaufene Transfers zum Bereinigen gefunden')

        if not dry_run:
            cleaned = clean_expired_transfers()
            self.stdout.write(
                self.style.SUCCESS(f'{cleaned} abgelaufene Transfers erfolgreich bereinigt')
            )
        else:
            self.stdout.write(f'Würde {count} Transfers bereinigen')

            for transfer in expired_transfers[:10]:  # Zeige die ersten 10
                self.stdout.write(
                    f'  - Transfer {transfer.id}: {transfer.title or "Ohne Titel"} '
                    f'(abgelaufen {transfer.expires_at})'
                )
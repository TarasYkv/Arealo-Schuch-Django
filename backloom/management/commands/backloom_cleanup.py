"""
Management Command für BackLoom Cleanup
Löscht alte Backlink-Quellen (älter als 12 Monate)

Usage:
    python manage.py backloom_cleanup
    python manage.py backloom_cleanup --months 6  # Quellen älter als 6 Monate
    python manage.py backloom_cleanup --dry-run   # Nur anzeigen, nicht löschen
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from backloom.models import BacklinkSource


class Command(BaseCommand):
    help = 'Löscht alte BackLoom Backlink-Quellen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=12,
            help='Lösche Quellen älter als X Monate (Standard: 12)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur anzeigen, nicht tatsächlich löschen'
        )

    def handle(self, *args, **options):
        months = options['months']
        dry_run = options['dry_run']

        cutoff_date = timezone.now() - timedelta(days=months * 30)

        # Alte Quellen finden
        old_sources = BacklinkSource.objects.filter(last_found__lt=cutoff_date)
        count = old_sources.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'Keine Quellen älter als {months} Monate gefunden.')
            )
            return

        self.stdout.write(f'Gefunden: {count} Quellen älter als {months} Monate')
        self.stdout.write(f'Stichtag: {cutoff_date.strftime("%d.%m.%Y")}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - Keine Änderungen vorgenommen'))

            # Beispiele anzeigen
            self.stdout.write('\nBeispiele der zu löschenden Quellen:')
            for source in old_sources[:10]:
                self.stdout.write(f'  - {source.domain} (zuletzt: {source.last_found.strftime("%d.%m.%Y")})')

            if count > 10:
                self.stdout.write(f'  ... und {count - 10} weitere')

        else:
            # Tatsächlich löschen
            deleted, _ = old_sources.delete()
            self.stdout.write(
                self.style.SUCCESS(f'{deleted} alte Backlink-Quellen gelöscht.')
            )

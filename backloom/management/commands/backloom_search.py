"""
Management Command für BackLoom Backlink-Suche
Kann per Cronjob oder manuell ausgeführt werden

Usage:
    python manage.py backloom_search
    python manage.py backloom_search --init-queries  # Suchbegriffe initialisieren
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from backloom.services import run_backlink_search, initialize_default_queries

User = get_user_model()


class Command(BaseCommand):
    help = 'Führt eine BackLoom Backlink-Suche durch'

    def add_arguments(self, parser):
        parser.add_argument(
            '--init-queries',
            action='store_true',
            help='Initialisiert die vordefinierten Suchbegriffe vor der Suche'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username des ausführenden Users (für Protokollierung)'
        )

    def handle(self, *args, **options):
        # User für Protokollierung
        user = None
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(f"User '{options['user']}' nicht gefunden, verwende System")
                )

        # Suchbegriffe initialisieren falls gewünscht
        if options['init_queries']:
            self.stdout.write('Initialisiere vordefinierte Suchbegriffe...')
            created = initialize_default_queries()
            self.stdout.write(
                self.style.SUCCESS(f'{created} neue Suchbegriffe erstellt')
            )

        # Suche starten
        self.stdout.write('Starte BackLoom Backlink-Suche...')
        self.stdout.write('Dies kann einige Minuten dauern...')

        try:
            search = run_backlink_search(user)

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=== SUCHE ABGESCHLOSSEN ==='))
            self.stdout.write(f'Gefunden: {search.sources_found}')
            self.stdout.write(f'Neu: {search.new_sources}')
            self.stdout.write(f'Aktualisiert: {search.updated_sources}')
            if search.duration_formatted:
                self.stdout.write(f'Dauer: {search.duration_formatted}')

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Fehler bei der Suche: {e}')
            )
            raise

"""
Management command to clean up old app usage tracking data
Run: python manage.py cleanup_app_usage_tracking
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import AppUsageTracking


class Command(BaseCommand):
    help = 'Clean up old app usage tracking data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Keep tracking data for the last N days (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting anything',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - Keine Daten werden gelöscht')
            )
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Finde alte Tracking-Daten
        old_records = AppUsageTracking.objects.filter(
            session_start__lt=cutoff_date
        )
        
        count = old_records.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Keine Tracking-Daten älter als {days} Tage gefunden.')
            )
            return
        
        self.stdout.write(f'📊 Gefundene alte Tracking-Daten:')
        self.stdout.write(f'   Cutoff-Datum: {cutoff_date.strftime("%d.%m.%Y %H:%M:%S")}')
        self.stdout.write(f'   Anzahl Datensätze: {count:,}')
        
        # Statistiken über die zu löschenden Daten
        stats_by_user = old_records.values('user__username').distinct().count()
        stats_by_app = {}
        
        for record in old_records.values('app_name').distinct():
            app_name = record['app_name']
            app_count = old_records.filter(app_name=app_name).count()
            stats_by_app[app_name] = app_count
        
        self.stdout.write(f'   Betroffene Benutzer: {stats_by_user}')
        self.stdout.write(f'   Apps/Features:')
        for app_name, app_count in sorted(stats_by_app.items(), key=lambda x: x[1], reverse=True):
            tracking = AppUsageTracking()
            tracking.app_name = app_name
            app_display = tracking.get_app_display_name()
            self.stdout.write(f'     - {app_display}: {app_count:,} Datensätze')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(f'📋 DRY RUN Zusammenfassung: {count:,} Datensätze würden gelöscht')
            )
            return
        
        # Bestätigung einholen (außer bei --force)
        if not force:
            self.stdout.write('')
            confirm = input(f'Möchten Sie {count:,} Tracking-Datensätze löschen? (ja/nein): ')
            if confirm.lower() not in ['ja', 'j', 'yes', 'y']:
                self.stdout.write(self.style.WARNING('❌ Löschvorgang abgebrochen.'))
                return
        
        # Lösche die Daten
        self.stdout.write('')
        self.stdout.write('🗑️ Lösche alte Tracking-Daten...')
        
        deleted_count, deleted_details = old_records.delete()
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'✅ {deleted_count:,} Tracking-Datensätze erfolgreich gelöscht!')
        )
        
        # Zeige Details der gelöschten Daten
        if deleted_details:
            self.stdout.write('')
            self.stdout.write('📋 Gelöschte Daten im Detail:')
            for model, count in deleted_details.items():
                if count > 0:
                    self.stdout.write(f'   - {model}: {count:,} Datensätze')
        
        # Zeige aktuelle Statistiken
        remaining_count = AppUsageTracking.objects.count()
        self.stdout.write('')
        self.stdout.write(f'📊 Verbleibende Tracking-Daten: {remaining_count:,}')
        
        if remaining_count > 0:
            oldest_remaining = AppUsageTracking.objects.order_by('session_start').first()
            newest_remaining = AppUsageTracking.objects.order_by('-session_start').first()
            
            self.stdout.write(f'   Ältester Datensatz: {oldest_remaining.session_start.strftime("%d.%m.%Y %H:%M:%S")}')
            self.stdout.write(f'   Neuester Datensatz: {newest_remaining.session_start.strftime("%d.%m.%Y %H:%M:%S")}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('🎉 Bereinigung der App-Nutzungsdaten abgeschlossen!')
        )
        
        # Empfehlung für regelmäßige Bereinigung
        self.stdout.write('')
        self.stdout.write('💡 Empfehlung:')
        self.stdout.write('   Fügen Sie diesen Befehl zu einem Cron-Job hinzu für regelmäßige Bereinigung:')
        self.stdout.write(f'   0 2 * * 0 python manage.py cleanup_app_usage_tracking --days {days} --force')
        self.stdout.write('   (läuft jeden Sonntag um 2:00 Uhr)')
"""
Django Management Command für automatische tägliche Datenbank-Backups

Verwendung:
    python manage.py daily_database_backup

Features:
    - Erstellt tägliches Backup der Datenbank
    - Unterstützt MySQL und SQLite
    - Automatische Rotation: Behält nur die letzten 30 Tage
    - Löscht automatisch ältere Backups
    - Kann als Scheduled Task auf PythonAnywhere eingerichtet werden
"""

import os
import subprocess
import shutil
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Erstellt ein automatisches Datenbank-Backup und löscht alte Backups (älter als 30 Tage)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-days',
            type=int,
            default=30,
            help='Anzahl der Tage, die Backups aufbewahrt werden sollen (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt nur an, welche Backups gelöscht würden, ohne sie tatsächlich zu löschen'
        )

    def handle(self, *args, **options):
        retention_days = options['retention_days']
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS('=== Automatisches Datenbank-Backup ==='))
        self.stdout.write(f'Retention: {retention_days} Tage')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - Keine Änderungen werden vorgenommen'))

        # 1. Erstelle Backup
        try:
            backup_file = self.create_backup()
            self.stdout.write(self.style.SUCCESS(f'✓ Backup erstellt: {backup_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Backup fehlgeschlagen: {str(e)}'))
            raise CommandError(f'Backup creation failed: {str(e)}')

        # 2. Lösche alte Backups
        try:
            deleted_count = self.cleanup_old_backups(retention_days, dry_run)
            if deleted_count > 0:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'→ Würde {deleted_count} alte Backup(s) löschen'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'✓ {deleted_count} alte Backup(s) gelöscht'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Keine alten Backups zum Löschen'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠ Cleanup-Warnung: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n=== Backup abgeschlossen ==='))

    def get_database_config(self):
        """Ermittelt Datenbank-Engine und Konfiguration"""
        db_config = settings.DATABASES['default']
        engine = db_config['ENGINE']

        if 'mysql' in engine:
            return {
                'engine': 'mysql',
                'name': db_config.get('NAME'),
                'user': db_config.get('USER'),
                'password': db_config.get('PASSWORD'),
                'host': db_config.get('HOST', 'localhost'),
                'port': db_config.get('PORT', 3306),
            }
        elif 'sqlite' in engine:
            return {
                'engine': 'sqlite',
                'path': db_config.get('NAME'),
            }
        else:
            raise CommandError(f'Unsupported database engine: {engine}')

    def create_backup(self):
        """Erstellt Datenbank-Backup"""
        # Backup-Verzeichnis erstellen
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Datenbank-Konfiguration ermitteln
        db_config = self.get_database_config()
        engine = db_config['engine']

        # Timestamp für Dateinamen
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if engine == 'mysql':
            # MySQL Backup mit mysqldump
            backup_filename = f'auto_backup_{timestamp}.sql'
            backup_path = os.path.join(backup_dir, backup_filename)

            cmd = [
                'mysqldump',
                '-h', db_config['host'],
                '-P', str(db_config['port']),
                '-u', db_config['user'],
                '--single-transaction',  # Konsistentes Backup ohne Table Locks
                '--quick',  # Schnellerer Export
                '--lock-tables=false',  # Keine Table Locks
                db_config['name']
            ]

            # Passwort via Umgebungsvariable (sicher)
            env = os.environ.copy()
            env['MYSQL_PWD'] = db_config['password']

            self.stdout.write(f'Erstelle MySQL Backup...')
            with open(backup_path, 'w') as backup_file:
                result = subprocess.run(
                    cmd,
                    stdout=backup_file,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )

            if result.returncode != 0:
                raise CommandError(f'mysqldump failed: {result.stderr}')

        elif engine == 'sqlite':
            # SQLite Backup mit File Copy
            backup_filename = f'auto_backup_{timestamp}.sqlite3'
            backup_path = os.path.join(backup_dir, backup_filename)

            db_path = db_config['path']
            self.stdout.write(f'Erstelle SQLite Backup...')
            shutil.copy2(db_path, backup_path)

        # Backup-Größe ermitteln
        backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB
        self.stdout.write(f'Backup-Größe: {backup_size:.2f} MB')

        return backup_filename

    def cleanup_old_backups(self, retention_days, dry_run=False):
        """Löscht Backups, die älter als retention_days sind"""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')

        if not os.path.exists(backup_dir):
            return 0

        # Grenzwert-Datum berechnen
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0

        self.stdout.write(f'\nPrüfe Backups älter als {cutoff_date.strftime("%Y-%m-%d")}...')

        # Alle Backup-Dateien durchgehen
        for filename in os.listdir(backup_dir):
            # Nur automatische Backups berücksichtigen
            if not filename.startswith('auto_backup_'):
                continue

            file_path = os.path.join(backup_dir, filename)

            # Nur Dateien (keine Verzeichnisse)
            if not os.path.isfile(file_path):
                continue

            # Dateierstellungsdatum ermitteln
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

            # Prüfen ob zu alt
            if file_mtime < cutoff_date:
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                age_days = (datetime.now() - file_mtime).days

                if dry_run:
                    self.stdout.write(
                        f'  → {filename} ({age_days} Tage alt, {file_size:.2f} MB)'
                    )
                else:
                    os.remove(file_path)
                    self.stdout.write(
                        f'  ✗ Gelöscht: {filename} ({age_days} Tage alt, {file_size:.2f} MB)'
                    )

                deleted_count += 1

        return deleted_count

"""
Django Management Command für tägliche Datenbank-Backups auf PythonAnywhere.
"""

import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path


class Command(BaseCommand):
    help = 'Erstellt ein Backup der Datenbank'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='~/backups',
            help='Verzeichnis für Backup-Dateien (Standard: ~/backups)'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=7,
            help='Anzahl Tage, die Backups behalten werden (Standard: 7)'
        )
        parser.add_argument(
            '--method',
            type=str,
            choices=['mysqldump', 'dumpdata'],
            default='mysqldump',
            help='Backup-Methode: mysqldump (schneller) oder dumpdata (portabler)'
        )

    def handle(self, *args, **options):
        output_dir = os.path.expanduser(options['output_dir'])
        keep_days = options['keep_days']
        method = options['method']

        # Stelle sicher, dass das Backup-Verzeichnis existiert
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generiere Dateinamen mit Timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if method == 'mysqldump':
            backup_file = os.path.join(output_dir, f'workloom_backup_{timestamp}.sql')
            self.backup_with_mysqldump(backup_file)
        else:
            backup_file = os.path.join(output_dir, f'workloom_backup_{timestamp}.json')
            self.backup_with_dumpdata(backup_file)

        # Lösche alte Backups
        self.cleanup_old_backups(output_dir, keep_days)

        self.stdout.write(
            self.style.SUCCESS(f'✓ Backup erfolgreich erstellt: {backup_file}')
        )

    def backup_with_mysqldump(self, backup_file):
        """Erstellt ein MySQL-Dump der Datenbank."""
        # Hole Datenbank-Konfiguration
        db_config = settings.DATABASES['default']

        if db_config['ENGINE'] != 'django.db.backends.mysql':
            self.stdout.write(
                self.style.WARNING('Warnung: MySQL-Dump nur für MySQL-Datenbanken möglich.')
            )
            return self.backup_with_dumpdata(backup_file.replace('.sql', '.json'))

        # Erstelle mysqldump Command
        command = [
            'mysqldump',
            '-h', db_config['HOST'] or 'localhost',
            '-u', db_config['USER'],
            f"-p{db_config['PASSWORD']}",  # Passwort direkt übergeben (keine Leerzeichen!)
        ]

        if db_config.get('PORT'):
            command.extend(['-P', str(db_config['PORT'])])

        # Datenbank-Name hinzufügen
        command.append(db_config['NAME'])

        self.stdout.write(f'Erstelle MySQL-Dump: {backup_file}')

        # Führe mysqldump aus und schreibe in Datei
        try:
            with open(backup_file, 'w') as f:
                result = subprocess.run(
                    command,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )

            if result.returncode != 0:
                self.stdout.write(
                    self.style.ERROR(f'Fehler bei mysqldump: {result.stderr}')
                )
                raise Exception(f'mysqldump fehlgeschlagen: {result.stderr}')

            # Komprimiere das Backup
            self.stdout.write('Komprimiere Backup...')
            subprocess.run(['gzip', backup_file], check=True)
            backup_file = f'{backup_file}.gz'

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Backup fehlgeschlagen: {str(e)}'))
            raise

    def backup_with_dumpdata(self, backup_file):
        """Erstellt ein Django dumpdata Backup."""
        from django.core import management

        self.stdout.write(f'Erstelle Django Dumpdata: {backup_file}')

        # Wichtige Apps die gesichert werden sollen
        apps_to_backup = [
            'accounts',
            'core',
            'pricing',
            'superconfig',
            'loomconnect',
            'mydash',
            'shop',
            'sites',
            'myarea'
        ]

        try:
            with open(backup_file, 'w') as f:
                management.call_command(
                    'dumpdata',
                    *apps_to_backup,
                    indent=2,
                    stdout=f,
                    exclude=['contenttypes', 'auth.permission', 'sessions']
                )

            # Komprimiere das Backup
            self.stdout.write('Komprimiere Backup...')
            subprocess.run(['gzip', backup_file], check=True)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Dumpdata fehlgeschlagen: {str(e)}'))
            raise

    def cleanup_old_backups(self, backup_dir, keep_days):
        """Löscht Backups die älter als keep_days sind."""
        import glob
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)

        # Finde alle Backup-Dateien
        backup_files = glob.glob(os.path.join(backup_dir, 'workloom_backup_*.gz'))
        backup_files.extend(glob.glob(os.path.join(backup_dir, 'workloom_backup_*.sql')))
        backup_files.extend(glob.glob(os.path.join(backup_dir, 'workloom_backup_*.json')))

        deleted_count = 0
        for backup_file in backup_files:
            # Extrahiere Timestamp aus Dateinamen
            filename = os.path.basename(backup_file)
            try:
                # Format: workloom_backup_YYYYMMDD_HHMMSS
                date_str = filename.split('_')[2] + filename.split('_')[3].split('.')[0]
                file_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')

                if file_date < cutoff_date:
                    os.remove(backup_file)
                    deleted_count += 1
                    self.stdout.write(f'Altes Backup gelöscht: {filename}')
            except (IndexError, ValueError):
                # Dateiname passt nicht zum erwarteten Format
                continue

        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ {deleted_count} alte Backups gelöscht')
            )
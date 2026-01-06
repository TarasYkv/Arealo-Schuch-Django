"""
Management Command: Verarbeitet ausstehende MyCut Exports.

Usage:
    python manage.py process_exports              # Einmalig ausfuehren
    python manage.py process_exports --daemon     # Als Always-on Task (Loop)
    python manage.py process_exports --job-id=24  # Spezifischen Job
"""

import os
import sys
import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

# Unbuffered output fuer Always-on Task Logs
sys.stdout = sys.stderr = open(sys.stdout.fileno(), 'w', buffering=1)


class Command(BaseCommand):
    help = 'Verarbeitet ausstehende MyCut Export Jobs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job-id',
            type=int,
            help='Spezifische Job ID verarbeiten',
        )
        parser.add_argument(
            '--max-jobs',
            type=int,
            default=5,
            help='Maximale Anzahl Jobs pro Durchlauf (default: 5)',
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Als Daemon laufen (fuer Always-on Task)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=10,
            help='Sekunden zwischen Checks im Daemon-Modus (default: 10)',
        )

    def handle(self, *args, **options):
        print(f"[{timezone.now().strftime('%H:%M:%S')}] process_exports handle() gestartet", flush=True)

        from mycut.models import ExportJob
        from mycut.tasks import export_step

        print(f"[{timezone.now().strftime('%H:%M:%S')}] Imports geladen", flush=True)

        job_id = options.get('job_id')
        max_jobs = options.get('max_jobs', 5)
        daemon_mode = options.get('daemon', False)
        interval = options.get('interval', 10)

        print(f"[{timezone.now().strftime('%H:%M:%S')}] Options: daemon={daemon_mode}, max_jobs={max_jobs}", flush=True)

        if daemon_mode:
            self.stdout.write(self.style.SUCCESS(
                f'Export Worker gestartet (prueft alle {interval}s)'
            ))
            self._run_daemon(export_step, max_jobs, interval)
        elif job_id:
            # Spezifischen Job verarbeiten
            try:
                job = ExportJob.objects.get(id=job_id)
                self._process_job(job, export_step)
            except ExportJob.DoesNotExist:
                self.stderr.write(f'Job {job_id} nicht gefunden')
                return
        else:
            # Alle ausstehenden Jobs verarbeiten
            self._process_pending_jobs(export_step, max_jobs)

    def _run_daemon(self, export_step, max_jobs, interval):
        """Laeuft als Daemon und prueft regelmaessig auf neue Jobs."""
        from mycut.models import ExportJob
        from django.db import connection

        print(f"[{timezone.now().strftime('%H:%M:%S')}] Daemon Loop startet...", flush=True)

        error_count = 0
        max_errors = 10  # Nach 10 Fehlern in Folge beenden
        loop_count = 0

        while True:
            loop_count += 1
            if loop_count <= 3 or loop_count % 30 == 0:  # Erste 3 und dann alle 5 Min
                print(f"[{timezone.now().strftime('%H:%M:%S')}] Loop #{loop_count}", flush=True)
            try:
                # WICHTIG: Verbindung VOR jeder DB-Abfrage schliessen und neu oeffnen
                # PythonAnywhere MySQL trennt inaktive Verbindungen nach ~5 Min
                connection.close()

                pending_jobs = list(ExportJob.objects.filter(
                    status__in=['pending', 'processing']
                ).order_by('created_at')[:max_jobs])

                if pending_jobs:
                    self.stdout.write(f'\n[{timezone.now().strftime("%H:%M:%S")}] {len(pending_jobs)} Job(s) gefunden')
                    for job in pending_jobs:
                        try:
                            # Frische DB-Verbindung vor jedem Job
                            connection.close()
                            job.refresh_from_db()
                            self._process_job(job, export_step)
                            error_count = 0  # Reset bei Erfolg
                        except Exception as job_error:
                            self.stderr.write(f'Fehler bei Job {job.id}: {job_error}')
                            logger.exception(f'Job {job.id} failed')
                            # Frische Verbindung fuer Fehler-Update
                            try:
                                connection.close()
                                job.refresh_from_db()
                                job.status = 'failed'
                                job.error_message = str(job_error)[:500]
                                job.save(update_fields=['status', 'error_message'])
                            except Exception:
                                pass
                            error_count += 1

                # Warten bis zum naechsten Check
                time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write('\nWorker beendet.')
                break
            except Exception as e:
                error_count += 1
                self.stderr.write(f'Fehler im Daemon ({error_count}/{max_errors}): {e}')
                logger.exception('Daemon error')

                if error_count >= max_errors:
                    self.stderr.write('Zu viele Fehler - Worker beendet sich.')
                    break

                # Bei Fehler: Verbindung schliessen
                try:
                    connection.close()
                except Exception:
                    pass

                time.sleep(30)  # Bei Fehler laenger warten

    def _process_pending_jobs(self, export_step, max_jobs):
        """Verarbeitet alle ausstehenden Jobs einmalig."""
        from mycut.models import ExportJob

        pending_jobs = ExportJob.objects.filter(
            status__in=['pending', 'processing']
        ).order_by('created_at')[:max_jobs]

        if not pending_jobs:
            self.stdout.write('Keine ausstehenden Export Jobs')
            return

        self.stdout.write(f'{len(pending_jobs)} ausstehende Jobs gefunden')

        for job in pending_jobs:
            self._process_job(job, export_step)

    def _process_job(self, job, export_step):
        """Verarbeitet einen einzelnen Export Job bis zum Ende."""
        self.stdout.write(f'\n=== Job {job.id} (Project {job.project_id}) ===')
        self.stdout.write(f'Status: {job.status}, Progress: {job.progress}%')

        if job.status == 'completed':
            self.stdout.write(self.style.SUCCESS('Bereits abgeschlossen'))
            return

        if job.status == 'failed':
            self.stdout.write(self.style.WARNING('Bereits fehlgeschlagen'))
            return

        max_iterations = 20  # Sicherheitslimit
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            self.stdout.write(f'\n  Step {iteration}...')

            try:
                result = export_step(job.project_id, job.id)

                status = result.get('status', 'unknown')
                progress = result.get('progress', 0)
                message = result.get('message', '')
                next_step = result.get('next_step', '')

                self.stdout.write(f'    Status: {status}, Progress: {progress}%')
                if message:
                    self.stdout.write(f'    Message: {message}')
                if next_step:
                    self.stdout.write(f'    Next: {next_step}')

                if status == 'completed':
                    self.stdout.write(self.style.SUCCESS(
                        f'\n  Job {job.id} erfolgreich abgeschlossen!'
                    ))
                    return

                if status == 'failed':
                    error = result.get('error', 'Unbekannter Fehler')
                    self.stdout.write(self.style.ERROR(
                        f'\n  Job {job.id} fehlgeschlagen: {error}'
                    ))
                    return

                # Kurze Pause zwischen Steps
                time.sleep(0.5)

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'\n  Fehler bei Job {job.id}: {str(e)}'
                ))
                logger.exception(f'Export job {job.id} failed')

                # Job als fehlgeschlagen markieren
                job.refresh_from_db()
                job.status = 'failed'
                job.error_message = str(e)[:500]
                job.save()
                return

        self.stdout.write(self.style.WARNING(
            f'\n  Job {job.id}: Max iterations ({max_iterations}) erreicht'
        ))

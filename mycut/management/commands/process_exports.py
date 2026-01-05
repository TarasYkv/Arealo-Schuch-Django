"""
Management Command: Verarbeitet ausstehende MyCut Exports.

Kann als Scheduled Task auf PythonAnywhere laufen (z.B. alle 5 Minuten).

Usage:
    python manage.py process_exports
    python manage.py process_exports --job-id=24
"""

import os
import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


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

    def handle(self, *args, **options):
        from mycut.models import ExportJob
        from mycut.tasks import export_step

        job_id = options.get('job_id')
        max_jobs = options.get('max_jobs', 5)

        if job_id:
            # Spezifischen Job verarbeiten
            try:
                job = ExportJob.objects.get(id=job_id)
                self._process_job(job, export_step)
            except ExportJob.DoesNotExist:
                self.stderr.write(f'Job {job_id} nicht gefunden')
                return
        else:
            # Alle ausstehenden Jobs verarbeiten
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

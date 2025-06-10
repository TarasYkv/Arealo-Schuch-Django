# Kompletter Inhalt für: pdf_sucher/management/commands/cleanup_pdfs.py

import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    # Eine kurze Hilfe-Beschreibung, die angezeigt wird, wenn man `python manage.py help cleanup_pdfs` ausführt.
    help = 'Löscht temporär gespeicherte PDF-Dateien aus dem Media-Ordner, die älter als 24 Stunden sind.'

    def handle(self, *args, **options):
        """
        Die Hauptlogik des Befehls.
        """
        # Zeitgrenze in Sekunden (24 Stunden * 60 Minuten * 60 Sekunden)
        # Sie können diesen Wert anpassen, z.B. auf 3600 für eine Stunde.
        zeitgrenze_sekunden = 24 * 60 * 60

        # Der Pfad zu Ihrem Media-Ordner, wie in settings.py definiert
        media_pfad = settings.MEDIA_ROOT

        if not os.path.isdir(media_pfad):
            self.stdout.write(
                self.style.WARNING(f"Der Media-Ordner '{media_pfad}' existiert nicht. Überspringe den Vorgang."))
            return

        jetzt_timestamp = time.time()
        dateien_geloescht = 0

        self.stdout.write("Starte die Bereinigung alter PDF-Dateien...")

        # Gehe durch alle Dateien im Media-Ordner
        for dateiname in os.listdir(media_pfad):
            # Wir interessieren uns nur für PDF-Dateien
            if dateiname.endswith(".pdf"):
                voller_pfad = os.path.join(media_pfad, dateiname)

                try:
                    # Hole den Zeitstempel der letzten Änderung der Datei
                    datei_aenderung_timestamp = os.path.getmtime(voller_pfad)

                    # Prüfe, ob die Datei älter als unsere Zeitgrenze ist
                    if (jetzt_timestamp - datei_aenderung_timestamp) > zeitgrenze_sekunden:
                        os.remove(voller_pfad)
                        self.stdout.write(self.style.SUCCESS(f"'{dateiname}' wurde gelöscht (älter als 24 Stunden)."))
                        dateien_geloescht += 1
                except OSError as e:
                    self.stdout.write(self.style.ERROR(f"Fehler beim Löschen von '{dateiname}': {e}"))

        self.stdout.write(
            self.style.SUCCESS(f"Bereinigung abgeschlossen. {dateien_geloescht} Dateien wurden gelöscht."))

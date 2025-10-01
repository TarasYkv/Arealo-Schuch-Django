from django.core.management.base import BaseCommand
from sportplatzApp.models import Komponente, Variante


class Command(BaseCommand):
    help = 'Erstellt die initialen Komponenten und Varianten für den Sportplatz-Konfigurator'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Komponenten und Varianten...\n')

        # Lösche alte Daten (optional)
        if self.confirm_deletion():
            Variante.objects.all().delete()
            Komponente.objects.all().delete()
            self.stdout.write(self.style.WARNING('Alte Daten gelöscht.'))

        # Erstelle Komponenten
        komponenten = self.create_komponenten()
        self.stdout.write(self.style.SUCCESS(f'{len(komponenten)} Komponenten erstellt.'))

        # Erstelle Varianten
        varianten = self.create_varianten(komponenten)
        self.stdout.write(self.style.SUCCESS(f'{len(varianten)} Varianten erstellt.'))

        self.stdout.write(self.style.SUCCESS('\n✅ Initialisierung abgeschlossen!'))

    def confirm_deletion(self):
        """Fragt ob bestehende Daten gelöscht werden sollen"""
        existing_count = Komponente.objects.count() + Variante.objects.count()
        if existing_count > 0:
            response = input(f'\n⚠️  Es existieren bereits {existing_count} Objekte. Löschen? (ja/nein): ')
            return response.lower() in ['ja', 'j', 'yes', 'y']
        return True

    def create_komponenten(self):
        """Erstellt alle notwendigen Komponenten"""
        komponenten_data = [
            # Leuchten (aus Excel-Tabelle)
            {
                'name': '7950 14404SP OP',
                'kategorie': 'LEUCHTE',
                'beschreibung': 'ON/OFF-Leuchte mit internem EVG'
            },
            {
                'name': '7950 14404SP DIMD OP',
                'kategorie': 'LEUCHTE',
                'beschreibung': 'DALI-Leuchte mit internem EVG (dimmbar)'
            },
            {
                'name': '7950 14404SP OP RFLO',
                'kategorie': 'LEUCHTE',
                'beschreibung': 'RFL-Leuchte mit internem EVG für Funksteuerung'
            },
            {
                'name': '7950 14404SP OV',
                'kategorie': 'LEUCHTE',
                'beschreibung': 'OV-Leuchte ohne internes EVG (für externe EVGs)'
            },

            # Traversen
            {
                'name': 'TR 900/108/170/4 M10/12',
                'kategorie': 'TRAVERSE',
                'beschreibung': 'Standard Traverse für Sportplatzbeleuchtung'
            },

            # Externe Vorschaltgeräte (EVG)
            {
                'name': 'EVG 900W',
                'kategorie': 'EVG',
                'beschreibung': 'Externes Vorschaltgerät 900W'
            },
            {
                'name': 'EVG 1200W',
                'kategorie': 'EVG',
                'beschreibung': 'Externes Vorschaltgerät 1200W (Premium)'
            },

            # Verteilerboxen
            {
                'name': '6VBOX TR',
                'kategorie': 'VERTEILERBOX',
                'beschreibung': 'Verteilerbox für Traversen-Montage'
            },

            # Steuerboxen
            {
                'name': 'VBOX RFL TR',
                'kategorie': 'STEUERBOX',
                'beschreibung': 'RFL Steuerbox für Funksteuerung (Traversen-Montage)'
            },

            # Steuerbausteine
            {
                'name': 'RFL LIMAS Air HUB TRI',
                'kategorie': 'STEUERBAUSTEIN',
                'beschreibung': 'LIMAS Air Funksteuerung-Modul (Tricolor)'
            },
        ]

        komponenten = {}
        for data in komponenten_data:
            komp, created = Komponente.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            komponenten[data['name']] = komp
            if created:
                self.stdout.write(f'  ✓ {data["name"]}')

        return komponenten

    def create_varianten(self, komponenten):
        """Erstellt alle Varianten basierend auf der Excel-Tabelle"""
        varianten_data = [
            {
                'name': 'Variante 1',
                'beschreibung': 'Günstigste Konfiguration - ON/OFF-Leuchten mit internem EVG',
                'leuchte': komponenten['7950 14404SP OP'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,  # Preise später hinzufügen
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': None,
                'anzahl_externe_evgs': 0,
                'preis_externe_evgs': None,
                'verteilerbox': komponenten['6VBOX TR'],
                'anzahl_verteilerboxen': 6,
                'preis_verteilerboxen': None,
                'steuerbox': None,
                'anzahl_steuerboxen': 0,
                'preis_steuerboxen': None,
                'steuerbaustein': None,
                'anzahl_steuerbausteine': 0,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Günstigste Konfiguration; Verteilerboxen nur optional'
            },
            {
                'name': 'Variante 2',
                'beschreibung': 'Kabelgebundene Steuerung DALI - DALI-Leuchten mit internem EVG',
                'leuchte': komponenten['7950 14404SP DIMD OP'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': None,
                'anzahl_externe_evgs': 0,
                'preis_externe_evgs': None,
                'verteilerbox': komponenten['6VBOX TR'],
                'anzahl_verteilerboxen': 6,
                'preis_verteilerboxen': None,
                'steuerbox': None,
                'anzahl_steuerboxen': 0,
                'preis_steuerboxen': None,
                'steuerbaustein': None,
                'anzahl_steuerbausteine': 0,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Kabelgebundene Steuerung DALI; Verteilerboxen nur optional'
            },
            {
                'name': 'Variante 3',
                'beschreibung': 'Funksteuerung LIMAS Air - Jede einzelne Leuchte ist steuerbar',
                'leuchte': komponenten['7950 14404SP OP RFLO'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': None,
                'anzahl_externe_evgs': 0,
                'preis_externe_evgs': None,
                'verteilerbox': komponenten['6VBOX TR'],
                'anzahl_verteilerboxen': 6,
                'preis_verteilerboxen': None,
                'steuerbox': None,
                'anzahl_steuerboxen': 0,
                'preis_steuerboxen': None,
                'steuerbaustein': komponenten['RFL LIMAS Air HUB TRI'],
                'anzahl_steuerbausteine': 16,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Funksteuerung LIMAS Air; Jede einzelne Leuchte ist steuerbar; Verteilerboxen nur optional'
            },
            {
                'name': 'Variante 4',
                'beschreibung': 'Günstigste Konfiguration mit externe EVGs',
                'leuchte': komponenten['7950 14404SP OV'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': komponenten['EVG 900W'],
                'anzahl_externe_evgs': 8,
                'preis_externe_evgs': None,
                'verteilerbox': komponenten['6VBOX TR'],
                'anzahl_verteilerboxen': 6,
                'preis_verteilerboxen': None,
                'steuerbox': None,
                'anzahl_steuerboxen': 0,
                'preis_steuerboxen': None,
                'steuerbaustein': None,
                'anzahl_steuerbausteine': 0,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Günstigste Konfiguration mit externe EVGs'
            },
            {
                'name': 'Variante 5',
                'beschreibung': 'Kabelgebundene Steuerung mit externe EVGs',
                'leuchte': komponenten['7950 14404SP OV'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': komponenten['EVG 900W'],
                'anzahl_externe_evgs': 8,
                'preis_externe_evgs': None,
                'verteilerbox': komponenten['6VBOX TR'],
                'anzahl_verteilerboxen': 6,
                'preis_verteilerboxen': None,
                'steuerbox': None,
                'anzahl_steuerboxen': 0,
                'preis_steuerboxen': None,
                'steuerbaustein': None,
                'anzahl_steuerbausteine': 0,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Kabelgebundene Steuerung mit externe EVGs'
            },
            {
                'name': 'Variante 6',
                'beschreibung': 'Funksteuerung mit externe EVGs - Immer 2 Leuchten gemeinsam steuerbar',
                'leuchte': komponenten['7950 14404SP OV'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': komponenten['EVG 900W'],
                'anzahl_externe_evgs': 8,
                'preis_externe_evgs': None,
                'verteilerbox': None,
                'anzahl_verteilerboxen': 0,
                'preis_verteilerboxen': None,
                'steuerbox': komponenten['VBOX RFL TR'],
                'anzahl_steuerboxen': 8,
                'preis_steuerboxen': None,
                'steuerbaustein': komponenten['RFL LIMAS Air HUB TRI'],
                'anzahl_steuerbausteine': 8,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Funksteuerung mit externe EVGs; immer 2 Leuchten sind gemeinsam steuerbar'
            },
            {
                'name': 'Variante 7',
                'beschreibung': 'Funksteuerung mit externe EVGs - Jede Leuchte einzeln steuerbar',
                'leuchte': komponenten['7950 14404SP OV'],
                'anzahl_leuchten': 16,
                'preis_leuchten': None,
                'traverse': komponenten['TR 900/108/170/4 M10/12'],
                'anzahl_traversen': 6,
                'preis_traversen': None,
                'externes_evg': komponenten['EVG 1200W'],
                'anzahl_externe_evgs': 8,
                'preis_externe_evgs': None,
                'verteilerbox': None,
                'anzahl_verteilerboxen': 0,
                'preis_verteilerboxen': None,
                'steuerbox': komponenten['VBOX RFL TR'],
                'anzahl_steuerboxen': 8,
                'preis_steuerboxen': None,
                'steuerbaustein': komponenten['RFL LIMAS Air HUB TRI'],
                'anzahl_steuerbausteine': 8,
                'preis_steuerbausteine': None,
                'bemerkung_konfiguration': 'Funksteuerung mit externe EVGs; jede Leuchte ist einzeln steuerbar'
            },
        ]

        varianten = []
        for data in varianten_data:
            # Berechne Gesamtpreis
            preis_gesamt = 0
            if data.get('preis_leuchten'):
                preis_gesamt += data['preis_leuchten']
            if data.get('preis_traversen'):
                preis_gesamt += data['preis_traversen']
            if data.get('preis_externe_evgs'):
                preis_gesamt += data['preis_externe_evgs']
            if data.get('preis_verteilerboxen'):
                preis_gesamt += data['preis_verteilerboxen']
            if data.get('preis_steuerboxen'):
                preis_gesamt += data['preis_steuerboxen']
            if data.get('preis_steuerbausteine'):
                preis_gesamt += data['preis_steuerbausteine']

            data['preis_gesamt'] = preis_gesamt

            variante, created = Variante.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            varianten.append(variante)
            if created:
                self.stdout.write(f'  ✓ {data["name"]} (Gesamt: {preis_gesamt:.2f} €)')

        return varianten

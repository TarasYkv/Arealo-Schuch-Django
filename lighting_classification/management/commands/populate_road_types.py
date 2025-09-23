from django.core.management.base import BaseCommand
from lighting_classification.models import RoadType


class Command(BaseCommand):
    help = 'Fügt die normgerechten Straßentypen nach DIN 13201-1:2021-09 in die Datenbank ein'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Straßentypen nach DIN 13201-1:2021-09...')

        road_types_data = [
            # Autobahnen und Kraftfahrstraßen
            {
                'code': 'A1',
                'name': 'Autobahn',
                'description': 'Kraftfahrzeugverkehr, getrennte Fahrtrichtungen, hohe Geschwindigkeit (>80 km/h)',
                'category': 'motorway',
                'lighting_type': 'M',
                'icon': 'highway'
            },
            {
                'code': 'A2',
                'name': 'Kraftfahrstraße',
                'description': 'Autobahnähnlich, aber geringere Anforderungen, mittlere bis hohe Geschwindigkeit',
                'category': 'motorway',
                'lighting_type': 'M',
                'icon': 'highway'
            },

            # Hauptverkehrsstraßen
            {
                'code': 'B1',
                'name': 'Hauptverkehrsstraße überörtlich',
                'description': 'Bundesstraßen, Landstraßen außerorts, überregionaler Verkehr',
                'category': 'main_road',
                'lighting_type': 'M',
                'icon': 'road'
            },
            {
                'code': 'B2',
                'name': 'Hauptverkehrsstraße örtlich',
                'description': 'Hauptstraßen in Ortschaften, hohe Verkehrsdichte',
                'category': 'main_road',
                'lighting_type': 'M',
                'icon': 'road'
            },
            {
                'code': 'B3',
                'name': 'Hauptverkehrsstraße mit ÖPNV',
                'description': 'Hauptstraßen mit Straßenbahn oder Busverkehr',
                'category': 'main_road',
                'lighting_type': 'Mixed',
                'icon': 'bus'
            },

            # Sammelstraßen
            {
                'code': 'C1',
                'name': 'Sammelstraße',
                'description': 'Verbindung zwischen Hauptstraßen, mittlere Verkehrsdichte',
                'category': 'collector',
                'lighting_type': 'M',
                'icon': 'route'
            },

            # Erschließungsstraßen
            {
                'code': 'C2',
                'name': 'Erschließungsstraße',
                'description': 'Wohngebiete, niedrige bis mittlere Geschwindigkeit (≤50 km/h)',
                'category': 'residential',
                'lighting_type': 'M',
                'icon': 'home'
            },
            {
                'code': 'C3',
                'name': 'Anliegerstraße',
                'description': 'Verkehrsberuhigt, Tempo 30, Wohnstraßen',
                'category': 'residential',
                'lighting_type': 'M',
                'icon': 'home'
            },

            # Konfliktbereiche
            {
                'code': 'D1',
                'name': 'Kreisverkehr',
                'description': 'Knotenpunkt, erhöhte Sicherheitsanforderungen',
                'category': 'conflict',
                'lighting_type': 'A',
                'icon': 'sync-alt'
            },
            {
                'code': 'D2',
                'name': 'Kreuzung/Einmündung',
                'description': 'Konfliktbereich verschiedener Verkehrsströme',
                'category': 'conflict',
                'lighting_type': 'A',
                'icon': 'intersection'
            },

            # Fußgängerwege
            {
                'code': 'E1',
                'name': 'Fußgängerzone',
                'description': 'Reine Fußgängernutzung, hohe Frequentierung',
                'category': 'pedestrian',
                'lighting_type': 'P',
                'icon': 'walking'
            },
            {
                'code': 'E2',
                'name': 'Fußgängerweg Hauptroute',
                'description': 'Stark frequentierte Fußgängerwege',
                'category': 'pedestrian',
                'lighting_type': 'P',
                'icon': 'walking'
            },
            {
                'code': 'E3',
                'name': 'Fußgängerweg Nebenroute',
                'description': 'Normal frequentierte Fußgängerwege',
                'category': 'pedestrian',
                'lighting_type': 'P',
                'icon': 'walking'
            },

            # Radwege
            {
                'code': 'F1',
                'name': 'Radweg eigenständig',
                'description': 'Separate Radinfrastruktur, keine Mischnutzung',
                'category': 'cycle',
                'lighting_type': 'P',
                'icon': 'bicycle'
            },
            {
                'code': 'F2',
                'name': 'Kombinierter Geh-/Radweg',
                'description': 'Gemeinsame Nutzung durch Fußgänger und Radfahrer',
                'category': 'cycle',
                'lighting_type': 'P',
                'icon': 'bicycle'
            },

            # Besondere Konfliktbereiche
            {
                'code': 'G1',
                'name': 'Zebrastreifen',
                'description': 'Fußgängerüberweg, erhöhte Sicherheitsanforderungen',
                'category': 'conflict',
                'lighting_type': 'A',
                'icon': 'pedestrian-crossing'
            },
            {
                'code': 'G2',
                'name': 'Bushaltestelle',
                'description': 'ÖPNV-Haltepunkt, Mischverkehr',
                'category': 'conflict',
                'lighting_type': 'Mixed',
                'icon': 'bus-stop'
            },
        ]

        created_count = 0
        updated_count = 0

        for road_data in road_types_data:
            road_type, created = RoadType.objects.get_or_create(
                code=road_data['code'],
                defaults=road_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Erstellt: {road_type.code} - {road_type.name}')
                )
            else:
                # Update existing record with new data
                for field, value in road_data.items():
                    if field != 'code':  # Don't update the code field
                        setattr(road_type, field, value)
                road_type.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'⟳ Aktualisiert: {road_type.code} - {road_type.name}')
                )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Abgeschlossen! {created_count} Straßentypen erstellt, {updated_count} aktualisiert.'
            )
        )
        self.stdout.write('Die Straßentypen sind jetzt nach DIN 13201-1:2021-09 verfügbar.')
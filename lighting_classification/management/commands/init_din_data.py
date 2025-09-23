from django.core.management.base import BaseCommand
from lighting_classification.models import (
    DINRoadCategory, DINClassificationParameter, DINParameterChoice, DINLightingClassStandard
)


class Command(BaseCommand):
    help = 'Initialisiert alle DIN 13201-1 konformen Daten'

    def handle(self, *args, **options):
        self.stdout.write('Initialisiere DIN 13201-1 konforme Daten...')

        self.create_road_categories()
        self.create_lighting_class_standards()
        self.create_autobahn_parameters()
        self.create_landstrasse_parameters()
        self.create_hauptverkehrsstrasse_parameters()
        self.create_sammelstrasse_parameters()
        self.create_erschliessung_sammelstrasse_parameters()
        self.create_erschliessung_anlieger_parameters()
        self.create_radwege_parameters()
        self.create_gehwege_parameters()
        self.create_plaetze_parameters()

        self.stdout.write(self.style.SUCCESS('DIN 13201-1 Daten erfolgreich initialisiert!'))

    def create_road_categories(self):
        """Straßenkategorien nach Tabelle 1"""
        categories = [
            {'code': 'AS', 'name': 'Autobahnen', 'description': 'Alle', 'lighting_class_type': 'M', 'table_number': 3},
            {'code': 'LS', 'name': 'Landstraßen (außerorts)', 'description': 'Alle', 'lighting_class_type': 'M', 'table_number': 4},
            {'code': 'HS', 'name': 'Hauptverkehrsstraßen', 'description': 'Ortsdurchfahrten, innergemeindliche Hauptverkehrsstraßen ≥50 km/h bis ≤70 km/h', 'lighting_class_type': 'M', 'table_number': 5},
            {'code': 'ES', 'name': 'Sammelstraßen', 'description': 'Sammelstraßen >30 km/h', 'lighting_class_type': 'M', 'table_number': 6},
            {'code': 'ES', 'name': 'Erschließungsstraßen Sammelstraße', 'description': 'Sammelstraßen ≤30 km/h', 'lighting_class_type': 'P', 'table_number': 7},
            {'code': 'ES', 'name': 'Erschließungsstraßen Anliegerstraße', 'description': 'Anliegerstraße und verkehrsberuhigte Fläche', 'lighting_class_type': 'P', 'table_number': 8},
            {'code': 'RADWEG', 'name': 'Radwege', 'description': 'Inner- und außergemeindliche Radverkehrsflächen', 'lighting_class_type': 'P', 'table_number': 9},
            {'code': 'GEHWEG', 'name': 'Gehwege', 'description': 'Inner- und außergemeindliche Gehwege', 'lighting_class_type': 'P', 'table_number': 10},
            {'code': 'PLATZ', 'name': 'Plätze', 'description': 'Plätze mit Bereichen des öffentlichen Personenverkehrs und Park- und Rastplätze', 'lighting_class_type': 'P', 'table_number': 11},
        ]

        for cat_data in categories:
            # Da ES mehrfach vorkommt, eindeutigen Namen erstellen
            if cat_data['table_number'] == 6:
                name = f"{cat_data['name']} >30km/h"
            elif cat_data['table_number'] == 7:
                name = f"{cat_data['name']} ≤30km/h"
            elif cat_data['table_number'] == 8:
                name = f"{cat_data['name']} verkehrsberuhigt"
            else:
                name = cat_data['name']

            category, created = DINRoadCategory.objects.get_or_create(
                code=f"{cat_data['code']}_{cat_data['table_number']}",
                defaults={
                    'name': name,
                    'description': cat_data['description'],
                    'lighting_class_type': cat_data['lighting_class_type'],
                    'table_number': cat_data['table_number']
                }
            )
            if created:
                self.stdout.write(f"Erstellt: {category}")

    def create_lighting_class_standards(self):
        """Beleuchtungsklassen-Standards nach DIN 13201-2:2015-11"""
        standards = [
            # M-Klassen
            {'class_type': 'M', 'class_number': 1, 'maintenance_luminance': 2.0, 'uo': 0.4, 'ul': 0.7, 'ti': 10},
            {'class_type': 'M', 'class_number': 2, 'maintenance_luminance': 1.5, 'uo': 0.4, 'ul': 0.7, 'ti': 10},
            {'class_type': 'M', 'class_number': 3, 'maintenance_luminance': 1.0, 'uo': 0.4, 'ul': 0.7, 'ti': 15},
            {'class_type': 'M', 'class_number': 4, 'maintenance_luminance': 0.75, 'uo': 0.4, 'ul': 0.7, 'ti': 15},
            {'class_type': 'M', 'class_number': 5, 'maintenance_luminance': 0.5, 'uo': 0.4, 'ul': 0.7, 'ti': 15},
            {'class_type': 'M', 'class_number': 6, 'maintenance_luminance': 0.3, 'uo': 0.4, 'ul': 0.7, 'ti': 15},

            # C-Klassen (bei q₀ = 0.07)
            {'class_type': 'C', 'class_number': 0, 'maintenance_illuminance': 50, 'uo': 0.4},
            {'class_type': 'C', 'class_number': 1, 'maintenance_illuminance': 30, 'uo': 0.4},
            {'class_type': 'C', 'class_number': 2, 'maintenance_illuminance': 20, 'uo': 0.4},
            {'class_type': 'C', 'class_number': 3, 'maintenance_illuminance': 15, 'uo': 0.4},
            {'class_type': 'C', 'class_number': 4, 'maintenance_illuminance': 10, 'uo': 0.4},
            {'class_type': 'C', 'class_number': 5, 'maintenance_illuminance': 7.5, 'uo': 0.4},

            # P-Klassen
            {'class_type': 'P', 'class_number': 1, 'maintenance_illuminance': 15, 'uo': 0.4},
            {'class_type': 'P', 'class_number': 2, 'maintenance_illuminance': 10, 'uo': 0.4},
            {'class_type': 'P', 'class_number': 3, 'maintenance_illuminance': 7.5, 'uo': 0.4},
            {'class_type': 'P', 'class_number': 4, 'maintenance_illuminance': 5, 'uo': 0.4},
            {'class_type': 'P', 'class_number': 5, 'maintenance_illuminance': 3, 'uo': 0.4},
            {'class_type': 'P', 'class_number': 6, 'maintenance_illuminance': 2, 'uo': 0.4},
        ]

        for std_data in standards:
            standard, created = DINLightingClassStandard.objects.get_or_create(
                class_type=std_data['class_type'],
                class_number=std_data['class_number'],
                defaults={
                    'maintenance_luminance': std_data.get('maintenance_luminance'),
                    'maintenance_illuminance': std_data.get('maintenance_illuminance'),
                    'overall_uniformity_uo': std_data['uo'],
                    'longitudinal_uniformity_ul': std_data.get('ul'),
                    'threshold_increment_ti': std_data.get('ti'),
                }
            )
            if created:
                self.stdout.write(f"Erstellt: Klasse {standard}")

    def create_autobahn_parameters(self):
        """Tabelle 3 - Autobahn Parameter"""
        category = DINRoadCategory.objects.get(code='AS_3')

        # Parameter erstellen
        parameters = [
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': False},
            {'type': 'junction_density', 'name': 'Abstand zwischen Knotenpunkten', 'is_variable': False},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                # Auswahlmöglichkeiten für jeden Parameter
                if param_data['type'] == 'speed_limit':
                    choices = [
                        {'text': '>100 km/h', 'value': 2, 'code': 'gt_100'},
                        {'text': '≤100 km/h', 'value': 1, 'code': 'lte_100'},
                    ]
                elif param_data['type'] == 'junction_density':
                    choices = [
                        {'text': '<3 km', 'value': 1, 'code': 'lt_3km'},
                        {'text': '≥3 km', 'value': 0, 'code': 'gte_3km'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_landstrasse_parameters(self):
        """Tabelle 4 - Landstraße außerorts Parameter"""
        category = DINRoadCategory.objects.get(code='LS_4')

        parameters = [
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': False},
            {'type': 'direction_separation', 'name': 'Trennung der Richtungsfahrbahnen', 'is_variable': False},
            {'type': 'junction_count', 'name': 'Anzahl Knotenpunkte', 'is_variable': False},
            {'type': 'traffic_volume', 'name': 'Verkehrsaufkommen', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'speed_limit':
                    choices = [
                        {'text': '>80 km/h', 'value': 1, 'code': 'gt_80'},
                        {'text': '≤80 km/h', 'value': 0, 'code': 'lte_80'},
                    ]
                elif param_data['type'] == 'direction_separation':
                    choices = [
                        {'text': 'Nein', 'value': 1, 'code': 'no'},
                        {'text': 'Ja', 'value': 0, 'code': 'yes'},
                    ]
                elif param_data['type'] == 'junction_count':
                    choices = [
                        {'text': '>3 je km', 'value': 1, 'code': 'gt_3_per_km'},
                        {'text': '≤3 je km', 'value': 0, 'code': 'lte_3_per_km'},
                    ]
                elif param_data['type'] == 'traffic_volume':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'gemischt, hoher Anteil nicht motorisiert', 'value': 2, 'code': 'mixed_high_non_motor'},
                        {'text': 'Gemischt', 'value': 1, 'code': 'mixed'},
                        {'text': 'nur motorisierter Verkehr', 'value': 0, 'code': 'motor_only'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_hauptverkehrsstrasse_parameters(self):
        """Tabelle 5 - Hauptverkehrsstraßen innerorts ≥50 km/h bis ≤70 km/h Parameter"""
        category = DINRoadCategory.objects.get(code='HS_5')

        parameters = [
            {'type': 'lanes_per_direction', 'name': 'Anzahl Fahrstreifen je Richtung', 'is_variable': False},
            {'type': 'direction_separation', 'name': 'Trennung der Richtungsfahrbahnen', 'is_variable': False},
            {'type': 'traffic_volume', 'name': 'Verkehrsaufkommen', 'is_variable': True},
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'parking_allowed', 'name': 'Parkende Fahrzeuge', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'lanes_per_direction':
                    choices = [
                        {'text': '>1', 'value': 1, 'code': 'gt_1'},
                        {'text': '1', 'value': 0, 'code': 'eq_1'},
                    ]
                elif param_data['type'] == 'direction_separation':
                    choices = [
                        {'text': 'Nein', 'value': 1, 'code': 'no'},
                        {'text': 'Ja', 'value': 0, 'code': 'yes'},
                    ]
                elif param_data['type'] == 'traffic_volume':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'speed_limit':
                    choices = [
                        {'text': '>30 km/h', 'value': 0, 'code': 'gt_30'},
                        {'text': 'reduziert auf ≤30 km/h', 'value': -1, 'code': 'reduced_lte_30'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'gemischt, hoher Anteil nicht motorisiert', 'value': 2, 'code': 'mixed_high_non_motor'},
                        {'text': 'Gemischt', 'value': 1, 'code': 'mixed'},
                        {'text': 'nur motorisierter Verkehr', 'value': 0, 'code': 'motor_only'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'parking_allowed':
                    choices = [
                        {'text': 'Zulässig', 'value': 1, 'code': 'allowed'},
                        {'text': 'nicht zulässig', 'value': 0, 'code': 'not_allowed'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_sammelstrasse_parameters(self):
        """Tabelle 6 - Sammelstraßen innerorts >30 km/h Parameter"""
        category = DINRoadCategory.objects.get(code='ES_6')

        parameters = [
            {'type': 'direction_separation', 'name': 'Trennung der Richtungsfahrbahnen', 'is_variable': False},
            {'type': 'traffic_volume', 'name': 'Verkehrsaufkommen', 'is_variable': True},
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'parking_allowed', 'name': 'Parkende Fahrzeuge', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'direction_separation':
                    choices = [
                        {'text': 'Nein', 'value': 0, 'code': 'no'},
                        {'text': 'Ja', 'value': -1, 'code': 'yes'},
                    ]
                else:
                    # Gleiche Choices wie Hauptverkehrsstraßen für variable Parameter
                    if param_data['type'] == 'traffic_volume':
                        choices = [
                            {'text': 'Normal', 'value': 0, 'code': 'normal'},
                            {'text': 'Gering', 'value': -1, 'code': 'low'},
                        ]
                    elif param_data['type'] == 'speed_limit':
                        choices = [
                            {'text': '>30 km/h', 'value': 0, 'code': 'gt_30'},
                            {'text': 'reduziert auf ≤30 km/h', 'value': -1, 'code': 'reduced_lte_30'},
                        ]
                    elif param_data['type'] == 'traffic_composition':
                        choices = [
                            {'text': 'gemischt, hoher Anteil nicht motorisiert', 'value': 2, 'code': 'mixed_high_non_motor'},
                            {'text': 'Gemischt', 'value': 1, 'code': 'mixed'},
                            {'text': 'nur motorisierter Verkehr', 'value': 0, 'code': 'motor_only'},
                        ]
                    elif param_data['type'] == 'ambient_luminance':
                        choices = [
                            {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                            {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                        ]
                    elif param_data['type'] == 'parking_allowed':
                        choices = [
                            {'text': 'Zulässig', 'value': 1, 'code': 'allowed'},
                            {'text': 'nicht zulässig', 'value': 0, 'code': 'not_allowed'},
                        ]
                    elif param_data['type'] == 'elevated_requirements':
                        choices = [
                            {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                            {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                        ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_erschliessung_sammelstrasse_parameters(self):
        """Tabelle 7 - Erschließungsstraßen ≤30 km/h (Sammelstraße) Parameter"""
        category = DINRoadCategory.objects.get(code='ES_7')

        parameters = [
            {'type': 'direction_separation', 'name': 'Trennung der Richtungsfahrbahnen', 'is_variable': False},
            {'type': 'traffic_volume', 'name': 'Verkehrsaufkommen', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'parking_allowed', 'name': 'Parkende Fahrzeuge', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
            {'type': 'face_recognition', 'name': 'Gesichtserkennung', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'direction_separation':
                    choices = [
                        {'text': 'Nein', 'value': 1, 'code': 'no'},
                        {'text': 'Ja', 'value': 0, 'code': 'yes'},
                    ]
                elif param_data['type'] == 'traffic_volume':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'gemischt, hoher Anteil nicht motorisiert', 'value': 1, 'code': 'mixed_high_non_motor'},
                        {'text': 'Gemischt', 'value': 0, 'code': 'mixed'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'parking_allowed':
                    choices = [
                        {'text': 'Zulässig', 'value': 1, 'code': 'allowed'},
                        {'text': 'nicht zulässig', 'value': 0, 'code': 'not_allowed'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]
                elif param_data['type'] == 'face_recognition':
                    choices = [
                        {'text': 'Erforderlich', 'value': 0, 'code': 'required'},  # zusätzliche Anforderungen
                        {'text': 'nicht erforderlich', 'value': 0, 'code': 'not_required'},  # keine zusätzlichen Anforderungen
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_erschliessung_anlieger_parameters(self):
        """Tabelle 8 - Erschließungsstraßen (Anliegerstraße, verkehrsberuhigte Fläche) Parameter"""
        category = DINRoadCategory.objects.get(code='ES_8')

        parameters = [
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': False},
            {'type': 'direction_separation', 'name': 'Trennung der Richtungsfahrbahnen', 'is_variable': False},
            {'type': 'traffic_volume', 'name': 'Verkehrsaufkommen', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'parking_allowed', 'name': 'Parkende Fahrzeuge', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
            {'type': 'face_recognition', 'name': 'Gesichtserkennung', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'speed_limit':
                    choices = [
                        {'text': '>30 km/h', 'value': 1, 'code': 'gt_30'},
                        {'text': '≤30 km/h', 'value': 0, 'code': 'lte_30'},
                        {'text': 'Schrittgeschwindigkeit', 'value': -1, 'code': 'walking_speed'},
                    ]
                elif param_data['type'] == 'direction_separation':
                    choices = [
                        {'text': 'Nein', 'value': 1, 'code': 'no'},
                        {'text': 'Ja', 'value': 0, 'code': 'yes'},
                    ]
                elif param_data['type'] == 'traffic_volume':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'gemischt, hoher Anteil nicht motorisiert', 'value': 1, 'code': 'mixed_high_non_motor'},
                        {'text': 'Gemischt', 'value': 0, 'code': 'mixed'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'parking_allowed':
                    choices = [
                        {'text': 'Zulässig', 'value': 1, 'code': 'allowed'},
                        {'text': 'nicht zulässig', 'value': 0, 'code': 'not_allowed'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]
                elif param_data['type'] == 'face_recognition':
                    choices = [
                        {'text': 'Erforderlich', 'value': 0, 'code': 'required'},
                        {'text': 'nicht erforderlich', 'value': 0, 'code': 'not_required'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_radwege_parameters(self):
        """Tabelle 9 - Radwege Parameter"""
        category = DINRoadCategory.objects.get(code='RADWEG_9')

        parameters = [
            {'type': 'operation_type', 'name': 'Betriebsart', 'is_variable': False},
            {'type': 'adjacent_areas_relation', 'name': 'Lagebezug zu angrenzenden Verkehrsflächen', 'is_variable': False},
            {'type': 'cycle_traffic_flow', 'name': 'Radverkehrsfluss', 'is_variable': True},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'operation_type':
                    choices = [
                        {'text': 'Zweirichtungsverkehr', 'value': 1, 'code': 'bidirectional'},
                        {'text': 'Einrichtungsverkehr', 'value': 0, 'code': 'unidirectional'},
                    ]
                elif param_data['type'] == 'adjacent_areas_relation':
                    choices = [
                        {'text': 'Sonstige', 'value': 1, 'code': 'other'},
                        {'text': 'bauliche Abgrenzung oder räumlich getrennt', 'value': 0, 'code': 'separated'},
                    ]
                elif param_data['type'] == 'cycle_traffic_flow':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'Radfahrer und Fußgänger', 'value': 1, 'code': 'cycle_pedestrian'},
                        {'text': 'reiner Radverkehr', 'value': 0, 'code': 'cycle_only'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_gehwege_parameters(self):
        """Tabelle 10 - Fußgängerflächen (Gehwege und Fußgängerzonen) Parameter"""
        category = DINRoadCategory.objects.get(code='GEHWEG_10')

        parameters = [
            {'type': 'walking_directions', 'name': 'Gehrichtungen', 'is_variable': False},
            {'type': 'traffic_composition', 'name': 'Verkehrsart/Zusammensetzung', 'is_variable': True},
            {'type': 'pedestrian_traffic_flow', 'name': 'Verkehrsfluss Fußgänger', 'is_variable': True},
            {'type': 'stay_function', 'name': 'Aufenthaltsfunktion', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
            {'type': 'face_recognition', 'name': 'Gesichtserkennung', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'walking_directions':
                    choices = [
                        {'text': 'mehrere verschiedene Gehrichtungen (z.B. Platzcharakter)', 'value': 1, 'code': 'multiple_directions'},
                        {'text': 'überwiegend linienhaft gehende Personen', 'value': 0, 'code': 'linear'},
                    ]
                elif param_data['type'] == 'traffic_composition':
                    choices = [
                        {'text': 'Gemischt', 'value': 1, 'code': 'mixed'},
                        {'text': 'nur Fußgänger', 'value': 0, 'code': 'pedestrian_only'},
                    ]
                elif param_data['type'] == 'pedestrian_traffic_flow':
                    choices = [
                        {'text': 'Normal', 'value': 0, 'code': 'normal'},
                        {'text': 'Gering', 'value': -1, 'code': 'low'},
                    ]
                elif param_data['type'] == 'stay_function':
                    choices = [
                        {'text': 'Bedeutsam', 'value': 1, 'code': 'significant'},
                        {'text': 'nicht relevant', 'value': 0, 'code': 'not_relevant'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'Homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'Vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]
                elif param_data['type'] == 'face_recognition':
                    choices = [
                        {'text': 'Erforderlich', 'value': 0, 'code': 'required'},
                        {'text': 'nicht erforderlich', 'value': 0, 'code': 'not_required'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )

    def create_plaetze_parameters(self):
        """Tabelle 11 - Plätze ≤30 km/h (Parkplatz, Rastanlage, Bahnhofsvorplatz, Busbahnhof) Parameter"""
        category = DINRoadCategory.objects.get(code='PLATZ_11')

        parameters = [
            {'type': 'speed_limit', 'name': 'Zulässige Geschwindigkeit', 'is_variable': False},
            {'type': 'pedestrian_traffic_flow', 'name': 'Verkehrsfluss, Fußgänger', 'is_variable': True},
            {'type': 'ambient_luminance', 'name': 'Leuchtdichte der Umgebung', 'is_variable': True},
            {'type': 'elevated_requirements', 'name': 'Erhöhte Anforderungen', 'is_variable': True},
            {'type': 'face_recognition', 'name': 'Gesichtserkennung', 'is_variable': True},
        ]

        for i, param_data in enumerate(parameters):
            param, created = DINClassificationParameter.objects.get_or_create(
                road_category=category,
                parameter_type=param_data['type'],
                defaults={
                    'name': param_data['name'],
                    'is_variable': param_data['is_variable'],
                    'order': i + 1
                }
            )

            if created:
                if param_data['type'] == 'speed_limit':
                    choices = [
                        {'text': '>Schrittgeschwindigkeit', 'value': 2, 'code': 'gt_walking_speed'},
                        {'text': 'Schrittgeschwindigkeit', 'value': 1, 'code': 'walking_speed'},
                    ]
                elif param_data['type'] == 'pedestrian_traffic_flow':
                    choices = [
                        {'text': 'Normal', 'value': 1, 'code': 'normal'},
                        {'text': 'Gering', 'value': 0, 'code': 'low'},
                    ]
                elif param_data['type'] == 'ambient_luminance':
                    choices = [
                        {'text': 'stark inhomogen', 'value': 0, 'code': 'strong_inhomogen'},
                        {'text': 'homogen', 'value': -1, 'code': 'homogen'},
                    ]
                elif param_data['type'] == 'elevated_requirements':
                    choices = [
                        {'text': 'vorhanden', 'value': 1, 'code': 'present'},
                        {'text': 'nicht vorhanden', 'value': 0, 'code': 'not_present'},
                    ]
                elif param_data['type'] == 'face_recognition':
                    choices = [
                        {'text': 'erforderlich', 'value': 0, 'code': 'required'},
                        {'text': 'nicht erforderlich', 'value': 0, 'code': 'not_required'},
                    ]

                for j, choice_data in enumerate(choices):
                    DINParameterChoice.objects.create(
                        parameter=param,
                        choice_text=choice_data['text'],
                        weighting_value=choice_data['value'],
                        choice_code=choice_data['code'],
                        order=j + 1
                    )
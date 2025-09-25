from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class RoadType(models.Model):
    """Straßentypen nach DIN 13201-1:2021-09"""

    CATEGORY_CHOICES = [
        ('motorway', 'Autobahnen und Kraftfahrstraßen'),
        ('main_road', 'Hauptverkehrsstraßen'),
        ('collector', 'Sammelstraßen'),
        ('residential', 'Erschließungsstraßen'),
        ('pedestrian', 'Fußgängerwege'),
        ('cycle', 'Radwege'),
        ('conflict', 'Konfliktbereiche'),
    ]

    code = models.CharField(max_length=10, unique=True, help_text="DIN-Code (z.B. A1, B2, C1)")
    name = models.CharField(max_length=100, help_text="Bezeichnung des Straßentyps")
    description = models.TextField(help_text="Detaillierte Beschreibung")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    lighting_type = models.CharField(max_length=20, choices=[
        ('M', 'M-Klassen (Kraftfahrzeugverkehr)'),
        ('P', 'P-Klassen (Fußgänger/Radfahrer)'),
        ('A', 'A-Klassen (Konfliktbereiche)'),
        ('Mixed', 'Gemischte Klassen'),
    ])
    icon = models.CharField(max_length=50, default='road', help_text="Font Awesome Icon Name")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']
        verbose_name = "Straßentyp"
        verbose_name_plural = "Straßentypen"

    def __str__(self):
        return f"{self.code} - {self.name}"


class LightingClassification(models.Model):
    """Beleuchtungsklassifizierung nach DIN 13201-1:2021-09"""

    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('completed', 'Abgeschlossen'),
        ('archived', 'Archiviert'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lighting_classifications')
    project_name = models.CharField(max_length=200, help_text="Name des Projekts")
    road_type = models.ForeignKey(RoadType, on_delete=models.CASCADE)

    # Parameter die je nach Straßentyp relevant sind
    traffic_volume = models.CharField(max_length=20, choices=[
        ('low', 'Niedrig (<500 Kfz/h)'),
        ('medium', 'Mittel (500-1500 Kfz/h)'),
        ('high', 'Hoch (>1500 Kfz/h)'),
    ], blank=True, null=True)

    speed_limit = models.CharField(max_length=20, choices=[
        ('30', '≤30 km/h'),
        ('50', '31-50 km/h'),
        ('80', '51-80 km/h'),
        ('unlimited', '>80 km/h'),
    ], blank=True, null=True)

    ambient_brightness = models.CharField(max_length=20, choices=[
        ('E0', 'E0 - Niedrig'),
        ('E1', 'E1 - Mittel'),
        ('E2', 'E2 - Hoch'),
    ], default='E0')

    usage_intensity = models.CharField(max_length=20, choices=[
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
    ], blank=True, null=True, help_text="Für Fußgänger-/Radwege")

    safety_requirements = models.CharField(max_length=20, choices=[
        ('normal', 'Normal'),
        ('elevated', 'Erhöht'),
        ('high', 'Hoch'),
    ], default='normal')

    special_conditions = models.TextField(blank=True, help_text="Besondere örtliche Gegebenheiten")

    # Ergebnis
    recommended_class = models.CharField(max_length=10, blank=True, help_text="Empfohlene Beleuchtungsklasse")
    luminance_value = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Leuchtdichte in cd/m²")
    illuminance_value = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Beleuchtungsstärke in lx")
    uniformity_ratio = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, help_text="Gleichmäßigkeitsverhältnis")

    # Metadaten
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Zusätzliche Notizen")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Beleuchtungsklassifizierung"
        verbose_name_plural = "Beleuchtungsklassifizierungen"

    def __str__(self):
        return f"{self.project_name} - {self.road_type.code}"

    def calculate_lighting_class(self):
        """Berechnung der Beleuchtungsklasse basierend auf DIN 13201-1:2021-09"""
        # Diese Methode wird die normgerechte Klassifizierung implementieren
        # Vorerst eine einfache Logik

        if self.road_type.lighting_type == 'M':
            # M-Klassen für Kraftfahrzeugverkehr
            if self.road_type.code in ['A1']:
                return 'M1', 2.0, None, 0.4
            elif self.road_type.code in ['A2', 'B1']:
                return 'M2', 1.5, None, 0.4
            elif self.road_type.code in ['B2', 'B3']:
                return 'M3', 1.0, None, 0.4
            elif self.road_type.code in ['C1']:
                return 'M4', 0.75, None, 0.4
            elif self.road_type.code in ['C2']:
                return 'M5', 0.5, None, 0.4
            else:
                return 'M6', 0.3, None, 0.4

        elif self.road_type.lighting_type == 'P':
            # P-Klassen für Fußgänger/Radfahrer
            if self.usage_intensity == 'high':
                return 'P1', None, 15, 0.4
            elif self.usage_intensity == 'medium':
                return 'P3', None, 7.5, 0.4
            else:
                return 'P5', None, 3, 0.4

        elif self.road_type.lighting_type == 'A':
            # A-Klassen für Konfliktbereiche
            if self.safety_requirements == 'high':
                return 'A1', None, 15, 0.4
            else:
                return 'A3', None, 7.5, 0.4

        return 'M6', 0.3, None, 0.4  # Fallback


class ClassificationCriteria(models.Model):
    """Normative Klassifizierungskriterien nach DIN 13201-1:2021-09"""

    CRITERIA_TYPE_CHOICES = [
        ('traffic_volume', 'Verkehrsstärke'),
        ('speed', 'Geschwindigkeit'),
        ('complexity', 'Komplexität der Verkehrssituation'),
        ('ambient_light', 'Umgebungshelligkeit'),
        ('user_category', 'Nutzer-Kategorie'),
        ('conflict_frequency', 'Konflikthäufigkeit'),
        ('parking', 'Parken am Fahrbahnrand'),
        ('intersection', 'Kreuzungen und Einmündungen'),
    ]

    road_type = models.ForeignKey(RoadType, on_delete=models.CASCADE, related_name='criteria')
    criteria_type = models.CharField(max_length=50, choices=CRITERIA_TYPE_CHOICES)
    name = models.CharField(max_length=200, help_text="Bezeichnung des Kriteriums")
    description = models.TextField(help_text="Beschreibung gemäß Norm")
    points = models.IntegerField(help_text="Punktwert nach DIN 13201-1:2021-09")
    order = models.PositiveIntegerField(default=0, help_text="Reihenfolge in der Tabelle")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['road_type', 'criteria_type', 'order']
        verbose_name = "Klassifizierungskriterium"
        verbose_name_plural = "Klassifizierungskriterien"

    def __str__(self):
        return f"{self.road_type.code} - {self.name} ({self.points} Punkte)"


class ClassificationScoring(models.Model):
    """Punktebewertung einer Klassifizierung"""

    classification = models.OneToOneField(LightingClassification, on_delete=models.CASCADE, related_name='scoring')
    selected_criteria = models.ManyToManyField(ClassificationCriteria, blank=True)
    total_points = models.IntegerField(default=0, help_text="Gesamtpunktzahl")
    calculated_class = models.CharField(max_length=10, blank=True, help_text="Berechnete Beleuchtungsklasse")

    class Meta:
        verbose_name = "Klassifizierungsbewertung"
        verbose_name_plural = "Klassifizierungsbewertungen"

    def calculate_total_points(self):
        """Berechnet die Gesamtpunktzahl"""
        self.total_points = sum(criteria.points for criteria in self.selected_criteria.all())
        return self.total_points

    def determine_lighting_class(self):
        """Bestimmt die Beleuchtungsklasse basierend auf Punktzahl und Straßentyp"""
        total = self.calculate_total_points()

        # M-Klassen basierend auf Punktzahl
        if self.classification.road_type.lighting_type == 'M':
            if total >= 6:
                return 'M1'
            elif total >= 5:
                return 'M2'
            elif total >= 4:
                return 'M3'
            elif total >= 3:
                return 'M4'
            elif total >= 2:
                return 'M5'
            else:
                return 'M6'

        # P-Klassen basierend auf Punktzahl
        elif self.classification.road_type.lighting_type == 'P':
            if total >= 6:
                return 'P1'
            elif total >= 5:
                return 'P2'
            elif total >= 4:
                return 'P3'
            elif total >= 3:
                return 'P4'
            elif total >= 2:
                return 'P5'
            elif total >= 1:
                return 'P6'
            else:
                return 'P7'

        # A-Klassen basierend auf Punktzahl
        elif self.classification.road_type.lighting_type == 'A':
            if total >= 6:
                return 'A1'
            elif total >= 5:
                return 'A2'
            elif total >= 4:
                return 'A3'
            elif total >= 3:
                return 'A4'
            elif total >= 2:
                return 'A5'
            else:
                return 'A6'

        return 'M6'  # Fallback

    def save(self, *args, **kwargs):
        self.total_points = self.calculate_total_points()
        self.calculated_class = self.determine_lighting_class()
        super().save(*args, **kwargs)


# ========================================
# DIN-KONFORME MODELLE NACH DIN 13201-1
# ========================================

class DINRoadCategory(models.Model):
    """Straßenkategorien nach DIN 13201-1 Tabelle 1"""

    CATEGORY_CODES = [
        ('AS', 'Autobahnen'),
        ('LS', 'Landstraßen (außerorts)'),
        ('HS', 'Hauptverkehrsstraßen'),
        ('ES', 'Erschließungsstraßen'),
        ('RADWEG', 'Radwege'),
        ('GEHWEG', 'Gehwege'),
        ('PLATZ', 'Sonstige Verkehrsflächen/Plätze'),
    ]

    LIGHTING_CLASSES = [
        ('M', 'M-Klassen (Motorisierter Verkehr)'),
        ('C', 'C-Klassen (Konfliktbereiche)'),
        ('P', 'P-Klassen (Fußgänger/Radfahrer)'),
    ]

    code = models.CharField(max_length=10, choices=CATEGORY_CODES, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    lighting_class_type = models.CharField(max_length=1, choices=LIGHTING_CLASSES)
    table_number = models.IntegerField(help_text="Tabellennummer in DIN 13201-1")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['table_number']
        verbose_name = "DIN Straßenkategorie"
        verbose_name_plural = "DIN Straßenkategorien"

    def __str__(self):
        return f"Tabelle {self.table_number}: {self.get_code_display()}"


class DINClassificationParameter(models.Model):
    """Parameter für die Klassifizierung nach DIN 13201-1"""

    PARAMETER_TYPES = [
        # Geschwindigkeitsparameter
        ('speed_limit', 'Zulässige Geschwindigkeit'),

        # Geometrische Parameter
        ('junction_density', 'Knotenpunktdichte'),
        ('junction_count', 'Anzahl Knotenpunkte'),
        ('lanes_per_direction', 'Anzahl Fahrstreifen je Richtung'),
        ('direction_separation', 'Trennung der Richtungsfahrbahnen'),

        # Verkehrsparameter
        ('traffic_volume', 'Verkehrsaufkommen'),
        ('traffic_composition', 'Verkehrsart/Zusammensetzung'),
        ('operation_type', 'Betriebsart'),
        ('cycle_traffic_flow', 'Radverkehrsfluss'),
        ('pedestrian_traffic_flow', 'Verkehrsfluss Fußgänger'),

        # Umgebungsparameter
        ('ambient_luminance', 'Leuchtdichte der Umgebung'),
        ('parking_allowed', 'Parkende Fahrzeuge'),
        ('adjacent_areas_relation', 'Lagebezug zu angrenzenden Verkehrsflächen'),

        # Nutzungsparameter
        ('walking_directions', 'Gehrichtungen'),
        ('stay_function', 'Aufenthaltsfunktion'),
        ('face_recognition', 'Gesichtserkennung'),

        # Sicherheitsparameter
        ('elevated_requirements', 'Erhöhte Anforderungen'),
    ]

    IS_VARIABLE_CHOICES = [
        (False, 'Auswahlparameter (fest)'),
        (True, 'Variable Parameter (adaptive Beleuchtung)'),
    ]

    road_category = models.ForeignKey(DINRoadCategory, on_delete=models.CASCADE, related_name='parameters')
    parameter_type = models.CharField(max_length=50, choices=PARAMETER_TYPES)
    name = models.CharField(max_length=200, help_text="Parametername gemäß DIN")
    is_variable = models.BooleanField(choices=IS_VARIABLE_CHOICES, help_text="Variable Parameter können zeitabhängig verändert werden")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['road_category', 'is_variable', 'order']
        unique_together = ['road_category', 'parameter_type']
        verbose_name = "DIN Klassifizierungsparameter"
        verbose_name_plural = "DIN Klassifizierungsparameter"

    def __str__(self):
        variable_indicator = " (variabel)" if self.is_variable else ""
        return f"{self.road_category.code} - {self.name}{variable_indicator}"


class DINParameterChoice(models.Model):
    """Auswahlmöglichkeiten für Parameter mit Wichtungswerten"""

    parameter = models.ForeignKey(DINClassificationParameter, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=200, help_text="Auswahltext gemäß DIN")
    weighting_value = models.IntegerField(help_text="Wichtungswert (VW) gemäß DIN")
    choice_code = models.CharField(max_length=50, help_text="Eindeutiger Code für die Auswahl")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['parameter', 'order']
        unique_together = ['parameter', 'choice_code']
        verbose_name = "DIN Parameter Auswahlmöglichkeit"
        verbose_name_plural = "DIN Parameter Auswahlmöglichkeiten"

    def __str__(self):
        return f"{self.parameter.name}: {self.choice_text} (VW={self.weighting_value})"


class DINLightingClassification(models.Model):
    """100% DIN-konforme Beleuchtungsklassifizierung"""

    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('calculation_pending', 'Berechnung ausstehend'),
        ('completed', 'Abgeschlossen'),
        ('archived', 'Archiviert'),
    ]

    TIME_PERIOD_CHOICES = [
        ('dt0', 'Δt₀ (Bemessungsbeleuchtungsklasse)'),
        ('dt1', 'Δt₁ (Adaptive Beleuchtung 1)'),
        ('dt2', 'Δt₂ (Adaptive Beleuchtung 2)'),
    ]

    # Grunddaten
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    project_name = models.CharField(max_length=200)
    road_category = models.ForeignKey(DINRoadCategory, on_delete=models.CASCADE)

    # Zeitraum für adaptive Beleuchtung
    time_period = models.CharField(max_length=10, choices=TIME_PERIOD_CHOICES, default='dt0')
    time_period_description = models.CharField(max_length=200, blank=True, help_text="z.B. '05:00-20:00 Uhr'")

    # Berechnungsergebnisse
    total_weighting_value = models.IntegerField(default=0, help_text="Summe VWS")
    calculated_lighting_class = models.CharField(max_length=10, blank=True, help_text="Berechnete Klasse (M/C/P)")

    # Leuchtdichte/Beleuchtungsstärke nach DIN 13201-2:2015-11
    maintenance_luminance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Wartungswert Leuchtdichte [cd/m²]")
    maintenance_illuminance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Wartungswert Beleuchtungsstärke [lx]")

    # Gütemerkmale nach DIN 13201-2:2015-11
    overall_uniformity_uo = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True, help_text="Gesamtgleichmäßigkeit Uo")
    longitudinal_uniformity_ul = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True, help_text="Längsgleichmäßigkeit Ul")
    threshold_increment_ti = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Schwellenwerterhöhung TI [%]")
    edge_illuminance_ratio_rei = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Randbeleuchtungsstärkeverhältnis REI")

    # Metadaten
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "DIN Beleuchtungsklassifizierung"
        verbose_name_plural = "DIN Beleuchtungsklassifizierungen"

    def __str__(self):
        period = f" ({self.get_time_period_display()})" if self.time_period != 'dt0' else ""
        return f"{self.project_name} - {self.road_category.code}{period}"

    def calculate_lighting_class(self):
        """Berechnung nach DIN 13201-1: M/P = 6 - VWS"""
        total_vws = self.selected_choices.aggregate(
            total=models.Sum('choice__weighting_value')
        )['total'] or 0

        self.total_weighting_value = total_vws

        # Berechnung der Klasse nach DIN-Formel
        class_number = 6 - total_vws

        # Grenzen einhalten
        if class_number < 1:
            class_number = 1
        elif class_number > 6:
            class_number = 6

        # Klassentyp bestimmen
        class_type = self.road_category.lighting_class_type
        calculated_class = f"{class_type}{class_number}"

        self.calculated_lighting_class = calculated_class

        # Wartungswerte nach DIN 13201-2:2015-11 setzen
        self._set_maintenance_values(calculated_class)

        return calculated_class

    def _set_maintenance_values(self, lighting_class):
        """Wartungswerte nach DIN 13201-2:2015-11 Tabelle 1, 2, 3"""

        # M-Klassen Wartungswerte [cd/m²]
        m_class_values = {
            'M1': {'luminance': Decimal('2.0'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('10')},
            'M2': {'luminance': Decimal('1.5'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('10')},
            'M3': {'luminance': Decimal('1.0'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('15')},
            'M4': {'luminance': Decimal('0.75'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('15')},
            'M5': {'luminance': Decimal('0.5'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('15')},
            'M6': {'luminance': Decimal('0.3'), 'uo': Decimal('0.4'), 'ul': Decimal('0.7'), 'ti': Decimal('15')},
        }

        # C-Klassen Wartungswerte [lx] (bei q₀ = 0.07)
        c_class_values = {
            'C0': {'illuminance': Decimal('50'), 'uo': Decimal('0.4')},
            'C1': {'illuminance': Decimal('30'), 'uo': Decimal('0.4')},
            'C2': {'illuminance': Decimal('20'), 'uo': Decimal('0.4')},
            'C3': {'illuminance': Decimal('15'), 'uo': Decimal('0.4')},
            'C4': {'illuminance': Decimal('10'), 'uo': Decimal('0.4')},
            'C5': {'illuminance': Decimal('7.5'), 'uo': Decimal('0.4')},
        }

        # P-Klassen Wartungswerte [lx]
        p_class_values = {
            'P1': {'illuminance': Decimal('15'), 'uo': Decimal('0.4')},
            'P2': {'illuminance': Decimal('10'), 'uo': Decimal('0.4')},
            'P3': {'illuminance': Decimal('7.5'), 'uo': Decimal('0.4')},
            'P4': {'illuminance': Decimal('5'), 'uo': Decimal('0.4')},
            'P5': {'illuminance': Decimal('3'), 'uo': Decimal('0.4')},
            'P6': {'illuminance': Decimal('2'), 'uo': Decimal('0.4')},
        }

        if lighting_class in m_class_values:
            values = m_class_values[lighting_class]
            self.maintenance_luminance = values['luminance']
            self.overall_uniformity_uo = values['uo']
            self.longitudinal_uniformity_ul = values['ul']
            self.threshold_increment_ti = values['ti']
            self.maintenance_illuminance = None

        elif lighting_class in c_class_values:
            values = c_class_values[lighting_class]
            self.maintenance_illuminance = values['illuminance']
            self.overall_uniformity_uo = values['uo']
            self.maintenance_luminance = None

        elif lighting_class in p_class_values:
            values = p_class_values[lighting_class]
            self.maintenance_illuminance = values['illuminance']
            self.overall_uniformity_uo = values['uo']
            self.maintenance_luminance = None

    def save(self, *args, **kwargs):
        if self.pk:  # Nur bei Updates automatisch berechnen
            self.calculate_lighting_class()
        super().save(*args, **kwargs)


class DINSelectedParameterChoice(models.Model):
    """Ausgewählte Parameter für eine Klassifizierung"""

    classification = models.ForeignKey(DINLightingClassification, on_delete=models.CASCADE, related_name='selected_choices')
    parameter = models.ForeignKey(DINClassificationParameter, on_delete=models.CASCADE)
    choice = models.ForeignKey(DINParameterChoice, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['classification', 'parameter']
        verbose_name = "DIN Ausgewählter Parameter"
        verbose_name_plural = "DIN Ausgewählte Parameter"

    def __str__(self):
        return f"{self.classification.project_name}: {self.parameter.name} = {self.choice.choice_text}"


class DINAdaptiveLightingSet(models.Model):
    """Gruppe von Klassifizierungen für adaptive Beleuchtung"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=200)
    road_category = models.ForeignKey(DINRoadCategory, on_delete=models.CASCADE)

    # Bemessungsbeleuchtungsklasse (Δt₀)
    base_classification = models.OneToOneField(DINLightingClassification, on_delete=models.CASCADE, related_name='adaptive_set_as_base')

    # Adaptive Klassen (optional)
    adaptive_dt1 = models.OneToOneField(DINLightingClassification, on_delete=models.CASCADE, related_name='adaptive_set_as_dt1', null=True, blank=True)
    adaptive_dt2 = models.OneToOneField(DINLightingClassification, on_delete=models.CASCADE, related_name='adaptive_set_as_dt2', null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "DIN Adaptive Beleuchtungsgruppe"
        verbose_name_plural = "DIN Adaptive Beleuchtungsgruppen"

    def __str__(self):
        return f"Adaptive Beleuchtung: {self.project_name}"

    def validate_adaptive_classes(self):
        """Validiert dass adaptive Klassen nicht mehr als 3 Stufen von Basis abweichen"""
        base_num = int(self.base_classification.calculated_lighting_class[-1])

        errors = []

        if self.adaptive_dt1:
            dt1_num = int(self.adaptive_dt1.calculated_lighting_class[-1])
            if abs(base_num - dt1_num) > 3:
                errors.append(f"Δt₁ Klasse {self.adaptive_dt1.calculated_lighting_class} weicht mehr als 3 Stufen von Basis {self.base_classification.calculated_lighting_class} ab")

        if self.adaptive_dt2:
            dt2_num = int(self.adaptive_dt2.calculated_lighting_class[-1])
            if abs(base_num - dt2_num) > 3:
                errors.append(f"Δt₂ Klasse {self.adaptive_dt2.calculated_lighting_class} weicht mehr als 3 Stufen von Basis {self.base_classification.calculated_lighting_class} ab")

        return errors


class DINLightingClassStandard(models.Model):
    """Referenztabelle für Beleuchtungsklassen nach DIN 13201-2:2015-11"""

    LIGHTING_CLASS_TYPES = [
        ('M', 'M-Klassen'),
        ('C', 'C-Klassen'),
        ('P', 'P-Klassen'),
    ]

    class_type = models.CharField(max_length=1, choices=LIGHTING_CLASS_TYPES)
    class_number = models.IntegerField()

    # Wartungswerte
    maintenance_luminance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Wartungswert Leuchtdichte [cd/m²]")
    maintenance_illuminance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Wartungswert Beleuchtungsstärke [lx]")

    # Gütemerkmale
    overall_uniformity_uo = models.DecimalField(max_digits=4, decimal_places=3, help_text="Gesamtgleichmäßigkeit Uo")
    longitudinal_uniformity_ul = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True, help_text="Längsgleichmäßigkeit Ul (nur M-Klassen)")
    threshold_increment_ti = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Schwellenwerterhöhung TI [%] (nur M-Klassen)")

    class Meta:
        unique_together = ['class_type', 'class_number']
        ordering = ['class_type', 'class_number']
        verbose_name = "DIN Beleuchtungsklassen-Standard"
        verbose_name_plural = "DIN Beleuchtungsklassen-Standards"

    def __str__(self):
        return f"{self.class_type}{self.class_number}"

    @property
    def class_name(self):
        return f"{self.class_type}{self.class_number}"

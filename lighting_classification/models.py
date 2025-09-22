from django.db import models
from django.conf import settings
from django.utils import timezone


class RoadType(models.Model):
    """Straßentypen nach DIN EN 13201 Teil 1"""

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
    """Beleuchtungsklassifizierung nach DIN EN 13201"""

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
        """Berechnung der Beleuchtungsklasse basierend auf DIN EN 13201"""
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
    """Normative Klassifizierungskriterien nach DIN EN 13201 Teil 1"""

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
    points = models.IntegerField(help_text="Punktwert nach DIN EN 13201")
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

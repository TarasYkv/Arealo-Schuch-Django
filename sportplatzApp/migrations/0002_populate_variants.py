from django.db import models  # <-- DIESE ZEILE HAT SEHR WAHRSCHEINLICH GEFEHLT
from django.utils import timezone


class Komponente(models.Model):
    KATEGORIEN = [
        ('LEUCHTE', 'Leuchte'),
        ('TRAVERSE', 'Traverse'),
        ('EVG', 'Externes EVG'),
        ('VERTEILERBOX', 'Verteilerbox'),
        ('STEUERBOX', 'Steuerbox'),
        ('STEUERBAUSTEIN', 'Steuerbaustein'),
        ('SONSTIGES', 'Sonstiges'),
    ]
    name = models.CharField(max_length=200, verbose_name="Name der Komponente")
    kategorie = models.CharField(max_length=100, choices=KATEGORIEN, verbose_name="Kategorie")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")

    def __str__(self):
        return f"{self.name} ({self.get_kategorie_display()})"


class Variante(models.Model):
    name = models.CharField(max_length=200, verbose_name="Name der Variante")
    beschreibung = models.CharField(max_length=300, verbose_name="Beschreibung")
    preis_leuchten = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Preis für alle Leuchten")
    preis_traversen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                          verbose_name="Preis für alle Traversen")
    preis_externe_evgs = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             verbose_name="Preis für alle externen EVGs")
    preis_verteilerboxen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                               verbose_name="Preis für alle Verteilerboxen")
    preis_steuerboxen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                            verbose_name="Preis für alle Steuerboxen")
    preis_steuerbausteine = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                verbose_name="Preis für alle Steuerbausteine")
    preis_gesamt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       verbose_name="Preis für die gesamte Variante")
    anzahl_leuchten = models.IntegerField(default=16)
    leuchte = models.ForeignKey(Komponente, on_delete=models.PROTECT, related_name="leuchte_in_varianten",
                                limit_choices_to={'kategorie': 'LEUCHTE'})
    anzahl_traversen = models.IntegerField(default=6)
    traverse = models.ForeignKey(Komponente, on_delete=models.PROTECT, related_name="traverse_in_varianten",
                                 limit_choices_to={'kategorie': 'TRAVERSE'})
    anzahl_externe_evgs = models.IntegerField(default=0)
    externes_evg = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="evg_in_varianten", limit_choices_to={'kategorie': 'EVG'})
    anzahl_verteilerboxen = models.IntegerField(default=0)
    verteilerbox = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="verteilerbox_in_varianten",
                                     limit_choices_to={'kategorie': 'VERTEILERBOX'})
    anzahl_steuerboxen = models.IntegerField(default=0)
    steuerbox = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="steuerbox_in_varianten", limit_choices_to={'kategorie': 'STEUERBOX'})
    anzahl_steuerbausteine = models.IntegerField(default=0)
    steuerbaustein = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="steuerbaustein_in_varianten",
                                       limit_choices_to={'kategorie': 'STEUERBAUSTEIN'})
    bemerkung_konfiguration = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Projekt(models.Model):
    projekt_name = models.CharField(max_length=200, verbose_name="Projektname")
    projektort = models.CharField(max_length=200, verbose_name="Projektort")
    kunde = models.CharField(max_length=200, verbose_name="Kunde")
    datum = models.DateField(default=timezone.now, verbose_name="Datum")
    ansprechpartner_email = models.EmailField(verbose_name="E-Mail des Ansprechpartners")
    laenge = models.FloatField(verbose_name="Länge in Metern", default=105)
    breite = models.FloatField(verbose_name="Breite in Metern", default=68)
    ausgewaehlte_variante = models.ForeignKey(Variante, on_delete=models.SET_NULL, null=True, blank=True,
                                              verbose_name="Gewählte Konfigurations-Variante")
    erstellungsdatum = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.projekt_name} ({self.kunde})"
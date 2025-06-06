# in sportplatzApp/models.py

from django.db import models
from django.utils import timezone


# Das Komponente-Modell von vorher bleibt unverändert
class Komponente(models.Model):
    KATEGORIEN = [
        ('BELAG', 'Rasen & Beläge'),
        ('BEWÄSSERUNG', 'Bewässerungssysteme'),
        ('LICHT', 'Flutlicht'),
        ('AUSSTATTUNG', 'Ausstattung (Tore, etc.)'),
    ]

    name = models.CharField(max_length=200, verbose_name="Name der Komponente")
    kategorie = models.CharField(max_length=100, choices=KATEGORIEN, verbose_name="Kategorie")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")

    def __str__(self):
        return self.name


# ==============================================================================
# HIER BEGINNT DEIN NEUES, DETAILLIERTES PROJEKT-MODELL
# ==============================================================================
class Projekt(models.Model):
    # === Allgemeine Projektdaten ===
    projekt_name = models.CharField(max_length=200, verbose_name="Projektname")
    projektort = models.CharField(max_length=200, verbose_name="Projektort")
    kunde = models.CharField(max_length=200, verbose_name="Kunde")
    datum = models.DateField(default=timezone.now, verbose_name="Datum")
    ansprechpartner_email = models.EmailField(verbose_name="E-Mail des Ansprechpartners",
                                              help_text="Wird für den E-Mail-Versand am Ende verwendet.")

    # === Abmessungen ===
    laenge = models.FloatField(verbose_name="Länge in Metern", help_text="Spielfeldgröße nach Fifa 105 x 68 m",
                               default=105)
    breite = models.FloatField(verbose_name="Breite in Metern", default=68)

    # === Beleuchtung (Gewünscht) ===
    class Beleuchtungsklassen(models.TextChoices):
        KLASSE_I = 'I', 'Beleuchtungsklasse I'
        KLASSE_II = 'II', 'Beleuchtungsklasse II'
        KLASSE_III = 'III', 'Beleuchtungsklasse III (75 lx)'
        TRAINING = 'TRAINING', 'Trainingsbeleuchtung (30 lx)'

    gewuenschte_beleuchtungsklasse = models.CharField(max_length=20, choices=Beleuchtungsklassen.choices,
                                                      default=Beleuchtungsklassen.KLASSE_III,
                                                      verbose_name="Gewünschte Beleuchtungsklasse")
    anzahl_maste = models.IntegerField(verbose_name="Anzahl der Maste", default=6)
    masthoehe = models.FloatField(verbose_name="Masthöhe in Meter", default=16)
    mastabstand = models.FloatField(verbose_name="Mastabstand zu Spielfeld in Meter", default=3)

    # Ja/Nein-Fragen werden am besten als BooleanField abgebildet. 
    # null=True erlaubt eine "Weiß nicht"-Option und wird im Admin als Dropdown (Ja/Nein/Unbekannt) angezeigt.
    vorschaltgeraet_in_leuchte = models.BooleanField(null=True, blank=True,
                                                     verbose_name="Vorschaltgerät integriert in der Leuchte")
    vorschaltgeraet_im_mast = models.BooleanField(null=True, blank=True, verbose_name="Vorschaltgerät Einbau im Mast")
    anzahl_masttueren = models.IntegerField(verbose_name="Anzahl der Masttüren", default=1)
    vorschaltgeraet_anbau = models.BooleanField(null=True, blank=True, verbose_name="Vorschaltgerät Anbau")

    # === IST-Zustand Schaltung ===
    ist_schaltung_alle_zusammen = models.BooleanField(null=True, blank=True,
                                                      verbose_name="IST: Schaltung alle Leuchten zusammen")
    ist_schaltung_je_mast = models.BooleanField(null=True, blank=True, verbose_name="IST: Schaltung je Mast")
    ist_schaltung_je_leuchte = models.BooleanField(null=True, blank=True,
                                                   verbose_name="IST: Schaltung jede Leuchte einzeln")

    # === Wunsch-Schaltung ===
    wunsch_schaltung_je_mast = models.BooleanField(null=True, blank=True, verbose_name="Wunsch: Schaltung je Mast")
    wunsch_schaltung_je_leuchte = models.BooleanField(null=True, blank=True,
                                                      verbose_name="Wunsch: Schaltung jede Leuchte einzeln")
    wunsch_dimmbar = models.BooleanField(null=True, blank=True, verbose_name="Wunsch: Dimmbar (Dali)")
    wunsch_steuerung_per_app = models.BooleanField(null=True, blank=True,
                                                   verbose_name="Wunsch: Steuerung über Limas AIR (App Tablet/Handy)")

    # === Schritt 2: Komponentenauswahl ===
    ausgewaehlte_komponenten = models.ManyToManyField(Komponente, blank=True)

    erstellungsdatum = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.projekt_name} ({self.kunde})"
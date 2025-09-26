from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class LightingCalculation(models.Model):
    """
    Hauptmodel für Wirtschaftlichkeitsberechnung von LED-Beleuchtungssystemen
    Basiert auf LMS Calc
    """

    # Meta Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Schritt 1: Projektdaten
    firmenname = models.CharField(max_length=200, verbose_name="Firmenname")
    projektname = models.CharField(max_length=200, verbose_name="Projektname")
    strompreis = models.FloatField(default=0.30, verbose_name="Strompreis (€/kWh)")
    kontakt_name = models.CharField(max_length=200, blank=True, verbose_name="Ansprechpartner")
    kontakt_email = models.EmailField(blank=True, verbose_name="E-Mail")
    kontakt_telefon = models.CharField(max_length=50, blank=True, verbose_name="Telefon")

    # Anlagentyp
    ANLAGEN_TYP_CHOICES = [
        (1, 'Industriebeleuchtung'),
        (2, 'Straßenbeleuchtung'),
        (3, 'Kundenspezifisch'),
    ]
    anlagen_typ = models.IntegerField(choices=ANLAGEN_TYP_CHOICES, default=1, verbose_name="Anlagentyp")
    neue_anlage_vorhanden = models.BooleanField(default=True, verbose_name="Bestandsanlage vorhanden?")

    # Schritt 2: Bestandsanlage (Alt)
    alt_hersteller = models.CharField(max_length=200, blank=True, verbose_name="Hersteller (Bestand)")
    alt_modell = models.CharField(max_length=200, blank=True, verbose_name="Modell (Bestand)")
    alt_leistung = models.FloatField(default=0, verbose_name="Leistung pro Leuchte in W (Bestand)")
    alt_anzahl = models.IntegerField(default=0, verbose_name="Anzahl Leuchten (Bestand)")
    alt_stunden_pro_tag = models.FloatField(default=0, verbose_name="Betriebsstunden pro Tag (Bestand)")
    alt_tage_pro_jahr = models.IntegerField(default=250, verbose_name="Betriebstage pro Jahr (Bestand)")
    alt_wartungskosten = models.FloatField(default=0, verbose_name="Wartungskosten pro Jahr in € (Bestand)")
    alt_laufende_kosten = models.FloatField(default=0, verbose_name="Weitere laufende Kosten pro Jahr in € (Bestand)")

    # Schritt 3: Neue Anlage (LED)
    neu_hersteller = models.CharField(max_length=200, default="", verbose_name="Hersteller (Neu)")
    neu_modell = models.CharField(max_length=200, blank=True, verbose_name="Modell (Neu)")
    neu_leistung = models.FloatField(default=0, verbose_name="Leistung pro Leuchte in W (Neu)")
    neu_anzahl = models.IntegerField(default=0, verbose_name="Anzahl Leuchten (Neu)")
    neu_stunden_pro_tag = models.FloatField(default=0, verbose_name="Betriebsstunden pro Tag (Neu)")
    neu_tage_pro_jahr = models.IntegerField(default=250, verbose_name="Betriebstage pro Jahr (Neu)")
    neu_anschaffungskosten_pro_stueck = models.FloatField(default=0, verbose_name="Anschaffungskosten pro Leuchte in €")
    neu_installationskosten = models.FloatField(default=0, verbose_name="Installationskosten gesamt in €")
    neu_wartungskosten = models.FloatField(default=0, verbose_name="Wartungskosten pro Jahr in € (Neu)")
    neu_laufende_kosten = models.FloatField(default=0, verbose_name="Weitere laufende Kosten pro Jahr in € (Neu)")

    # Schritt 4: Lichtmanagementsystem (LMS)
    lms_aktiviert = models.BooleanField(default=False, verbose_name="Lichtmanagementsystem verwenden")
    lms_grundkosten = models.FloatField(default=0, verbose_name="LMS Grundkosten in €")
    lms_aufpreis_pro_leuchte = models.FloatField(default=0, verbose_name="LMS Aufpreis pro Leuchte in €")

    # Bewegungsmelder
    bewegungsmelder_aktiviert = models.BooleanField(default=False, verbose_name="Bewegungsmelder verwenden")
    bewegungsmelder_anzahl = models.IntegerField(default=0, verbose_name="Anzahl Leuchten mit Bewegungsmelder")
    bewegungsmelder_abwesenheit_niveau = models.IntegerField(default=20, verbose_name="Beleuchtungsniveau bei Abwesenheit (%)")
    bewegungsmelder_anwesenheit_niveau = models.IntegerField(default=100, verbose_name="Beleuchtungsniveau bei Anwesenheit (%)")
    bewegungsmelder_frequentierung_stunden = models.FloatField(default=4, verbose_name="Frequentierung in Stunden")
    bewegungsmelder_frequentierung_minuten = models.FloatField(default=0, verbose_name="Frequentierung zusätzliche Minuten")
    bewegungsmelder_mehrkosten = models.FloatField(default=0, verbose_name="Mehrkosten Bewegungsmelder in €")
    bewegungsmelder_fadein = models.IntegerField(default=5, verbose_name="Fade-In Zeit in Sekunden")
    bewegungsmelder_fadeout = models.IntegerField(default=5, verbose_name="Fade-Out Zeit in Sekunden")

    # Tageslichtabhängige Regelung
    tageslicht_aktiviert = models.BooleanField(default=False, verbose_name="Tageslichtabhängige Regelung verwenden")
    tageslicht_anzahl = models.IntegerField(default=0, verbose_name="Anzahl Leuchten mit Tageslichtregelung")
    tageslicht_reduzierung_niveau = models.FloatField(default=40, verbose_name="Reduzierungsniveau bei Tageslicht (%)")
    tageslicht_nutzung_stunden = models.FloatField(default=4, verbose_name="Tageslichtnutzung in Stunden")
    tageslicht_nutzung_minuten = models.FloatField(default=0, verbose_name="Tageslichtnutzung zusätzliche Minuten")
    tageslicht_mehrkosten = models.FloatField(default=0, verbose_name="Mehrkosten Tageslichtregelung in €")

    # Kalendersteuerung
    kalender_aktiviert = models.BooleanField(default=False, verbose_name="Kalendersteuerung verwenden")
    kalender_anzahl_ausschalttage = models.IntegerField(default=0, verbose_name="Anzahl Tage Ausschaltung (Feiertage etc.)")

    # Berechnete Felder (werden automatisch berechnet)
    # Verbrauch & Kosten Bestand
    verbrauch_alt_kwh_jahr = models.FloatField(null=True, blank=True, verbose_name="Verbrauch Bestand (kWh/Jahr)")
    kosten_alt_jahr = models.FloatField(null=True, blank=True, verbose_name="Gesamtkosten Bestand (€/Jahr)")

    # Verbrauch & Kosten Neu ohne LMS
    verbrauch_neu_ohne_lms_kwh_jahr = models.FloatField(null=True, blank=True, verbose_name="Verbrauch Neu ohne LMS (kWh/Jahr)")
    kosten_neu_ohne_lms_jahr = models.FloatField(null=True, blank=True, verbose_name="Kosten Neu ohne LMS (€/Jahr)")

    # Verbrauch & Kosten Neu mit LMS
    verbrauch_neu_mit_lms_kwh_jahr = models.FloatField(null=True, blank=True, verbose_name="Verbrauch Neu mit LMS (kWh/Jahr)")
    kosten_neu_mit_lms_jahr = models.FloatField(null=True, blank=True, verbose_name="Kosten Neu mit LMS (€/Jahr)")

    # Ersparnis & Amortisation
    ersparnis_neu_zu_alt_jahr = models.FloatField(null=True, blank=True, verbose_name="Ersparnis Neu zu Alt (€/Jahr)")
    ersparnis_lms_jahr = models.FloatField(null=True, blank=True, verbose_name="Ersparnis durch LMS (€/Jahr)")

    investitionskosten_gesamt = models.FloatField(null=True, blank=True, verbose_name="Gesamte Investitionskosten (€)")
    investitionskosten_lms = models.FloatField(null=True, blank=True, verbose_name="Investitionskosten LMS (€)")

    amortisation_neu_jahre = models.FloatField(null=True, blank=True, verbose_name="Amortisation Neue Anlage (Jahre)")
    amortisation_neu_monate = models.FloatField(null=True, blank=True, verbose_name="Amortisation Neue Anlage (Monate)")
    amortisation_lms_jahre = models.FloatField(null=True, blank=True, verbose_name="Amortisation LMS (Jahre)")
    amortisation_lms_monate = models.FloatField(null=True, blank=True, verbose_name="Amortisation LMS (Monate)")
    amortisation_gesamt_jahre = models.FloatField(null=True, blank=True, verbose_name="Amortisation Gesamt (Jahre)")
    amortisation_gesamt_monate = models.FloatField(null=True, blank=True, verbose_name="Amortisation Gesamt (Monate)")

    # CO2 Emissionen
    co2_emission_alt_kg_jahr = models.FloatField(null=True, blank=True, verbose_name="CO2 Emission Bestand (kg/Jahr)")
    co2_emission_neu_ohne_lms_kg_jahr = models.FloatField(null=True, blank=True, verbose_name="CO2 Emission Neu ohne LMS (kg/Jahr)")
    co2_emission_neu_mit_lms_kg_jahr = models.FloatField(null=True, blank=True, verbose_name="CO2 Emission Neu mit LMS (kg/Jahr)")
    co2_ersparnis_kg_jahr = models.FloatField(null=True, blank=True, verbose_name="CO2 Ersparnis (kg/Jahr)")

    class Meta:
        verbose_name = "Beleuchtungsberechnung"
        verbose_name_plural = "Beleuchtungsberechnungen"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.projektname} - {self.firmenname} ({self.created_at.strftime('%d.%m.%Y')})"

    def save(self, *args, **kwargs):
        # Hier werden später die Berechnungen durchgeführt
        self.calculate_all()
        super().save(*args, **kwargs)

    def calculate_all(self):
        """
        Führt alle Berechnungen durch basierend auf den Eingabedaten
        """
        from .calculation_service import LightingCalculationService
        service = LightingCalculationService(self)
        service.calculate_all()
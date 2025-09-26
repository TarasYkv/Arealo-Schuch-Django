"""
Berechnungsservice für Wirtschaftlichkeitsberechnungen von LED-Beleuchtungssystemen
Basiert auf LMS Calc Logik
"""

class LightingCalculationService:
    """
    Service-Klasse für alle Berechnungen der Wirtschaftlichkeitsanalyse
    """

    # Emissionsfaktoren (g/kWh) - Quelle: Umweltbundesamt 2017
    EMISSION_FACTORS = {
        'co2': 489,  # kg/MWh = g/kWh
        'so2': 0.260,  # g/kWh
        'nox': 0.449,  # g/kWh
        'staub': 0.019,  # g/kWh
        'pm10': 0.012,  # g/kWh
        'co': 0.159,  # g/kWh
        'n2o': 0.022,  # g/kWh
        'ch4': 0.028,  # g/kWh
        'nmvoc': 0.027,  # g/kWh
        'hg': 0.0000088,  # g/kWh
    }

    def __init__(self, calculation):
        """
        Initialisiert den Service mit einem LightingCalculation Objekt

        Args:
            calculation: LightingCalculation Model-Instanz
        """
        self.calc = calculation

    def calculate_all(self):
        """
        Führt alle Berechnungen durch und speichert die Ergebnisse im Model
        """
        # Schritt 1: Bestandsanlage berechnen
        self.calculate_existing_system()

        # Schritt 2: Neue Anlage ohne LMS berechnen
        self.calculate_new_system_without_lms()

        # Schritt 3: Neue Anlage mit LMS berechnen (wenn aktiviert)
        if self.calc.lms_aktiviert:
            self.calculate_new_system_with_lms()
        else:
            # Wenn LMS nicht aktiviert, sind die Werte gleich wie ohne LMS
            self.calc.verbrauch_neu_mit_lms_kwh_jahr = self.calc.verbrauch_neu_ohne_lms_kwh_jahr
            self.calc.kosten_neu_mit_lms_jahr = self.calc.kosten_neu_ohne_lms_jahr

        # Schritt 4: Ersparnis berechnen
        self.calculate_savings()

        # Schritt 5: Investitionskosten berechnen
        self.calculate_investment_costs()

        # Schritt 6: Amortisation berechnen
        self.calculate_amortization()

        # Schritt 7: CO2-Emissionen berechnen
        self.calculate_emissions()

    def calculate_existing_system(self):
        """
        Berechnet Verbrauch und Kosten der Bestandsanlage
        """
        if not self.calc.neue_anlage_vorhanden:
            self.calc.verbrauch_alt_kwh_jahr = 0
            self.calc.kosten_alt_jahr = 0
            return

        # Verbrauch = Leistung(kW) * Anzahl * Stunden/Tag * Tage/Jahr
        self.calc.verbrauch_alt_kwh_jahr = (
            (self.calc.alt_leistung / 1000) *  # W zu kW
            self.calc.alt_anzahl *
            self.calc.alt_stunden_pro_tag *
            self.calc.alt_tage_pro_jahr
        )

        # Kosten = Stromkosten + Wartungskosten + Laufende Kosten
        stromkosten = self.calc.verbrauch_alt_kwh_jahr * self.calc.strompreis
        self.calc.kosten_alt_jahr = (
            stromkosten +
            self.calc.alt_wartungskosten +
            self.calc.alt_laufende_kosten
        )

    def calculate_new_system_without_lms(self):
        """
        Berechnet Verbrauch und Kosten der neuen Anlage ohne LMS
        """
        # Verbrauch = Leistung(kW) * Anzahl * Stunden/Tag * Tage/Jahr
        self.calc.verbrauch_neu_ohne_lms_kwh_jahr = (
            (self.calc.neu_leistung / 1000) *  # W zu kW
            self.calc.neu_anzahl *
            self.calc.neu_stunden_pro_tag *
            self.calc.neu_tage_pro_jahr
        )

        # Kosten = Stromkosten + Wartungskosten + Laufende Kosten
        stromkosten = self.calc.verbrauch_neu_ohne_lms_kwh_jahr * self.calc.strompreis
        self.calc.kosten_neu_ohne_lms_jahr = (
            stromkosten +
            self.calc.neu_wartungskosten +
            self.calc.neu_laufende_kosten
        )

    def calculate_new_system_with_lms(self):
        """
        Berechnet Verbrauch und Kosten der neuen Anlage mit LMS
        Berücksichtigt Bewegungsmelder, Tageslichtregelung und Kalendersteuerung
        """
        verbrauch_gesamt = 0
        arbeitstage_effektiv = self.calc.neu_tage_pro_jahr

        # Kalendersteuerung berücksichtigen
        if self.calc.kalender_aktiviert:
            arbeitstage_effektiv -= self.calc.kalender_anzahl_ausschalttage

        # Arbeitstage in plausiblen Bereich bringen
        arbeitstage_effektiv = max(0, min(arbeitstage_effektiv, self.calc.neu_tage_pro_jahr))

        # Leistung pro Leuchte in kW
        leistung_pro_leuchte_kw = self.calc.neu_leistung / 1000

        # Ermitteln, wie viele Leuchten unter welche Steuerung fallen (ohne Überschneidung)
        bewegung_count = 0
        tageslicht_count = 0

        if self.calc.bewegungsmelder_aktiviert:
            bewegung_count = min(max(self.calc.bewegungsmelder_anzahl, 0), self.calc.neu_anzahl)

        verbleibende_leuchten = max(0, self.calc.neu_anzahl - bewegung_count)

        if self.calc.tageslicht_aktiviert:
            tageslicht_count = min(max(self.calc.tageslicht_anzahl, 0), verbleibende_leuchten)
            verbleibende_leuchten = max(0, verbleibende_leuchten - tageslicht_count)

        # 1. Leuchten mit Bewegungsmelder
        if bewegung_count > 0:
            verbrauch_bewegung = self._calculate_motion_sensor_consumption(
                leistung_pro_leuchte_kw,
                bewegung_count,
                arbeitstage_effektiv
            )
            verbrauch_gesamt += verbrauch_bewegung

        # 2. Leuchten mit Tageslichtregelung
        if tageslicht_count > 0:
            verbrauch_tageslicht = self._calculate_daylight_consumption(
                leistung_pro_leuchte_kw,
                tageslicht_count,
                arbeitstage_effektiv
            )
            verbrauch_gesamt += verbrauch_tageslicht

        # 3. Normale Leuchten (ohne Steuerung)
        normale_leuchten = max(0, verbleibende_leuchten)

        if normale_leuchten > 0:
            verbrauch_normal = (
                leistung_pro_leuchte_kw *
                normale_leuchten *
                self.calc.neu_stunden_pro_tag *
                arbeitstage_effektiv
            )
            verbrauch_gesamt += verbrauch_normal

        self.calc.verbrauch_neu_mit_lms_kwh_jahr = verbrauch_gesamt

        # Kosten berechnen
        stromkosten = verbrauch_gesamt * self.calc.strompreis
        self.calc.kosten_neu_mit_lms_jahr = (
            stromkosten +
            self.calc.neu_wartungskosten +
            self.calc.neu_laufende_kosten
        )

    def _calculate_motion_sensor_consumption(self, leistung_kw, anzahl, arbeitstage):
        """
        Berechnet den Verbrauch für Leuchten mit Bewegungsmelder

        Args:
            leistung_kw: Leistung pro Leuchte in kW
            anzahl: Anzahl der Leuchten mit Bewegungsmelder
            arbeitstage: Effektive Arbeitstage im Jahr

        Returns:
            float: Jahresverbrauch in kWh
        """
        # Frequentierung in Stunden umrechnen
        frequentierung_gesamt = (
            self.calc.bewegungsmelder_frequentierung_stunden +
            self.calc.bewegungsmelder_frequentierung_minuten / 60
        )

        frequentierung_gesamt = max(0, frequentierung_gesamt)
        frequentierung_gesamt = min(frequentierung_gesamt, self.calc.neu_stunden_pro_tag)

        # Verbrauch bei Abwesenheit
        abwesenheit_stunden = max(0, self.calc.neu_stunden_pro_tag - frequentierung_gesamt)
        verbrauch_abwesenheit = (
            leistung_kw *
            anzahl *
            abwesenheit_stunden *
            arbeitstage *
            (self.calc.bewegungsmelder_abwesenheit_niveau / 100)
        )

        # Verbrauch bei Anwesenheit
        verbrauch_anwesenheit = (
            leistung_kw *
            anzahl *
            frequentierung_gesamt *
            arbeitstage *
            (self.calc.bewegungsmelder_anwesenheit_niveau / 100)
        )

        return verbrauch_abwesenheit + verbrauch_anwesenheit

    def _calculate_daylight_consumption(self, leistung_kw, anzahl, arbeitstage):
        """
        Berechnet den Verbrauch für Leuchten mit Tageslichtregelung

        Args:
            leistung_kw: Leistung pro Leuchte in kW
            anzahl: Anzahl der Leuchten mit Tageslichtregelung
            arbeitstage: Effektive Arbeitstage im Jahr

        Returns:
            float: Jahresverbrauch in kWh
        """
        # Tageslichtnutzung in Stunden umrechnen
        tageslicht_stunden_gesamt = (
            self.calc.tageslicht_nutzung_stunden +
            self.calc.tageslicht_nutzung_minuten / 60
        )

        tageslicht_stunden_gesamt = max(0, tageslicht_stunden_gesamt)
        tageslicht_stunden_gesamt = min(tageslicht_stunden_gesamt, self.calc.neu_stunden_pro_tag)

        # Verbrauch während Tageslichtnutzung (reduziert)
        verbrauch_tageslicht_reduziert = (
            leistung_kw *
            anzahl *
            tageslicht_stunden_gesamt *
            arbeitstage *
            (self.calc.tageslicht_reduzierung_niveau / 100)
        )

        # Verbrauch ohne Tageslicht (volle Leistung)
        stunden_ohne_tageslicht = max(0, self.calc.neu_stunden_pro_tag - tageslicht_stunden_gesamt)
        verbrauch_ohne_tageslicht = (
            leistung_kw *
            anzahl *
            stunden_ohne_tageslicht *
            arbeitstage
        )

        return verbrauch_tageslicht_reduziert + verbrauch_ohne_tageslicht

    def calculate_savings(self):
        """
        Berechnet die Ersparnis durch neue Anlage und LMS
        """
        # Ersparnis Neu zu Alt
        if self.calc.neue_anlage_vorhanden:
            self.calc.ersparnis_neu_zu_alt_jahr = (
                self.calc.kosten_alt_jahr -
                self.calc.kosten_neu_ohne_lms_jahr
            )
        else:
            self.calc.ersparnis_neu_zu_alt_jahr = 0

        # Ersparnis durch LMS
        if self.calc.lms_aktiviert:
            self.calc.ersparnis_lms_jahr = (
                self.calc.kosten_neu_ohne_lms_jahr -
                self.calc.kosten_neu_mit_lms_jahr
            )
        else:
            self.calc.ersparnis_lms_jahr = 0

    def calculate_investment_costs(self):
        """
        Berechnet die Investitionskosten
        """
        # Gesamte Investitionskosten für neue Anlage
        self.calc.investitionskosten_gesamt = (
            self.calc.neu_anzahl * self.calc.neu_anschaffungskosten_pro_stueck +
            self.calc.neu_installationskosten
        )

        # Investitionskosten für LMS
        if self.calc.lms_aktiviert:
            self.calc.investitionskosten_lms = (
                self.calc.lms_grundkosten +
                self.calc.neu_anzahl * self.calc.lms_aufpreis_pro_leuchte +
                self.calc.bewegungsmelder_mehrkosten +
                self.calc.tageslicht_mehrkosten
            )
        else:
            self.calc.investitionskosten_lms = 0

    def calculate_amortization(self):
        """
        Berechnet die Amortisationszeiten
        """
        # Amortisation neue Anlage
        if self.calc.ersparnis_neu_zu_alt_jahr > 0:
            self.calc.amortisation_neu_jahre = (
                self.calc.investitionskosten_gesamt /
                self.calc.ersparnis_neu_zu_alt_jahr
            )
            self.calc.amortisation_neu_monate = self.calc.amortisation_neu_jahre * 12
        else:
            self.calc.amortisation_neu_jahre = None
            self.calc.amortisation_neu_monate = None

        # Amortisation LMS
        if self.calc.ersparnis_lms_jahr > 0 and self.calc.lms_aktiviert:
            self.calc.amortisation_lms_jahre = (
                self.calc.investitionskosten_lms /
                self.calc.ersparnis_lms_jahr
            )
            self.calc.amortisation_lms_monate = self.calc.amortisation_lms_jahre * 12
        else:
            self.calc.amortisation_lms_jahre = None
            self.calc.amortisation_lms_monate = None

        # Kombinierte Amortisation (neue Anlage + LMS)
        if self.calc.lms_aktiviert and self.calc.neue_anlage_vorhanden:
            gesamt_investition = (
                self.calc.investitionskosten_gesamt +
                self.calc.investitionskosten_lms
            )
            gesamt_ersparnis = (
                self.calc.ersparnis_neu_zu_alt_jahr +
                self.calc.ersparnis_lms_jahr
            )
            if gesamt_ersparnis > 0:
                self.calc.amortisation_gesamt_jahre = gesamt_investition / gesamt_ersparnis
                self.calc.amortisation_gesamt_monate = self.calc.amortisation_gesamt_jahre * 12
            else:
                self.calc.amortisation_gesamt_jahre = None
                self.calc.amortisation_gesamt_monate = None

    def calculate_emissions(self):
        """
        Berechnet die CO2-Emissionen und Ersparnis
        """
        # CO2-Faktor in kg/kWh
        co2_factor = self.EMISSION_FACTORS['co2'] / 1000

        # CO2-Emissionen Bestandsanlage
        if self.calc.neue_anlage_vorhanden:
            self.calc.co2_emission_alt_kg_jahr = (
                self.calc.verbrauch_alt_kwh_jahr * co2_factor
            )
        else:
            self.calc.co2_emission_alt_kg_jahr = 0

        # CO2-Emissionen neue Anlage ohne LMS
        self.calc.co2_emission_neu_ohne_lms_kg_jahr = (
            self.calc.verbrauch_neu_ohne_lms_kwh_jahr * co2_factor
        )

        # CO2-Emissionen neue Anlage mit LMS
        if self.calc.lms_aktiviert:
            self.calc.co2_emission_neu_mit_lms_kg_jahr = (
                self.calc.verbrauch_neu_mit_lms_kwh_jahr * co2_factor
            )
        else:
            self.calc.co2_emission_neu_mit_lms_kg_jahr = (
                self.calc.co2_emission_neu_ohne_lms_kg_jahr
            )

        # CO2-Ersparnis
        self.calc.co2_ersparnis_kg_jahr = (
            self.calc.co2_emission_alt_kg_jahr -
            self.calc.co2_emission_neu_mit_lms_kg_jahr
        )

    def get_all_emissions(self):
        """
        Berechnet alle Emissionen für verschiedene Schadstoffe

        Returns:
            dict: Dictionary mit allen Emissionswerten
        """
        emissions = {}

        for pollutant, factor in self.EMISSION_FACTORS.items():
            factor_kwh = factor / 1000 if pollutant == 'co2' else factor / 1000000

            emissions[pollutant] = {
                'alt': self.calc.verbrauch_alt_kwh_jahr * factor_kwh if self.calc.neue_anlage_vorhanden else 0,
                'neu_ohne_lms': self.calc.verbrauch_neu_ohne_lms_kwh_jahr * factor_kwh,
                'neu_mit_lms': self.calc.verbrauch_neu_mit_lms_kwh_jahr * factor_kwh if self.calc.lms_aktiviert else self.calc.verbrauch_neu_ohne_lms_kwh_jahr * factor_kwh,
                'einheit': 'kg/Jahr' if pollutant in ['co2', 'so2', 'nox'] else 'g/Jahr'
            }

        return emissions

    def validate_input(self):
        """
        Validiert die Eingabedaten auf Plausibilität

        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []

        # Strompreis prüfen
        if self.calc.strompreis <= 0 or self.calc.strompreis > 1:
            errors.append("Strompreis sollte zwischen 0 und 1 €/kWh liegen")

        # Betriebsstunden prüfen
        if self.calc.neu_stunden_pro_tag > 24:
            errors.append("Betriebsstunden pro Tag können nicht mehr als 24 sein")

        if self.calc.alt_stunden_pro_tag > 24:
            errors.append("Betriebsstunden pro Tag (Bestand) können nicht mehr als 24 sein")

        # Betriebstage prüfen
        if self.calc.neu_tage_pro_jahr > 365:
            errors.append("Betriebstage pro Jahr können nicht mehr als 365 sein")

        if self.calc.alt_tage_pro_jahr > 365:
            errors.append("Betriebstage pro Jahr (Bestand) können nicht mehr als 365 sein")

        # Bewegungsmelder Logik prüfen
        if self.calc.bewegungsmelder_aktiviert:
            if self.calc.bewegungsmelder_anzahl > self.calc.neu_anzahl:
                errors.append("Anzahl Bewegungsmelder-Leuchten kann nicht größer als Gesamtanzahl sein")

            if self.calc.bewegungsmelder_frequentierung_stunden > self.calc.neu_stunden_pro_tag:
                errors.append("Frequentierung kann nicht länger als Betriebsstunden sein")

        # Tageslicht Logik prüfen
        if self.calc.tageslicht_aktiviert:
            if self.calc.tageslicht_anzahl > self.calc.neu_anzahl:
                errors.append("Anzahl Tageslicht-Leuchten kann nicht größer als Gesamtanzahl sein")

            if self.calc.tageslicht_nutzung_stunden > self.calc.neu_stunden_pro_tag:
                errors.append("Tageslichtnutzung kann nicht länger als Betriebsstunden sein")

        # Überlappung prüfen – statt Fehler nur Hinweis, da Leuchten doppelt gezählt werden können
        # Überlappung zwischen Bewegungsmelder- und Tageslichtregelung
        # Falls beide Werte zusammen größer als die Gesamtanzahl sind, werden die Überschüsse
        # in der Berechnung automatisch ignoriert – daher hier kein Fehler.

        return len(errors) == 0, errors

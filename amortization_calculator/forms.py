from django import forms
from .models import LightingCalculation


class Step1ProjectDataForm(forms.ModelForm):
    """
    Schritt 1: Projektdaten und allgemeine Informationen
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'firmenname',
            'projektname',
            'strompreis',
            'kontakt_name',
            'kontakt_email',
            'kontakt_telefon',
            'anlagen_typ',
            'neue_anlage_vorhanden',
        ]
        widgets = {
            'firmenname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Musterfirma GmbH'}),
            'projektname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Hallensanierung 2024'}),
            'strompreis': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '1'}),
            'kontakt_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Vor- und Nachname'}),
            'kontakt_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@beispiel.de'}),
            'kontakt_telefon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+49 123 456789'}),
            'anlagen_typ': forms.Select(attrs={'class': 'form-control'}),
            'neue_anlage_vorhanden': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'strompreis': 'Aktueller Strompreis in €/kWh',
            'neue_anlage_vorhanden': 'Aktivieren, wenn eine Bestandsanlage zum Vergleich vorhanden ist',
        }


class Step2ExistingSystemForm(forms.ModelForm):
    """
    Schritt 2: Bestandsanlage (nur wenn vorhanden)
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'alt_hersteller',
            'alt_modell',
            'alt_leistung',
            'alt_anzahl',
            'alt_stunden_pro_tag',
            'alt_tage_pro_jahr',
            'alt_wartungskosten',
            'alt_laufende_kosten',
        ]
        widgets = {
            'alt_hersteller': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Philips, Osram'}),
            'alt_modell': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Modellbezeichnung'}),
            'alt_leistung': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'alt_anzahl': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'alt_stunden_pro_tag': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0', 'max': '24'}),
            'alt_tage_pro_jahr': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '365'}),
            'alt_wartungskosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'alt_laufende_kosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'alt_leistung': 'Leistungsaufnahme pro Leuchte in Watt',
            'alt_stunden_pro_tag': 'Durchschnittliche Betriebsstunden pro Tag',
            'alt_tage_pro_jahr': 'Betriebstage im Jahr (z.B. 250 für 5-Tage-Woche)',
            'alt_wartungskosten': 'Jährliche Wartungs- und Reparaturkosten in €',
            'alt_laufende_kosten': 'Weitere laufende Kosten pro Jahr in €',
        }


class Step3NewSystemForm(forms.ModelForm):
    """
    Schritt 3: Neue LED-Anlage
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'neu_hersteller',
            'neu_modell',
            'neu_leistung',
            'neu_anzahl',
            'neu_stunden_pro_tag',
            'neu_tage_pro_jahr',
            'neu_anschaffungskosten_pro_stueck',
            'neu_installationskosten',
            'neu_wartungskosten',
            'neu_laufende_kosten',
        ]
        widgets = {
            'neu_hersteller': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hersteller eingeben'}),
            'neu_modell': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. nD866'}),
            'neu_leistung': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'neu_anzahl': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'neu_stunden_pro_tag': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0', 'max': '24'}),
            'neu_tage_pro_jahr': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '365'}),
            'neu_anschaffungskosten_pro_stueck': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'neu_installationskosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'neu_wartungskosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'neu_laufende_kosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'neu_leistung': 'Leistungsaufnahme pro LED-Leuchte in Watt',
            'neu_anschaffungskosten_pro_stueck': 'Preis pro Leuchte in €',
            'neu_installationskosten': 'Gesamte Installationskosten in €',
            'neu_wartungskosten': 'Erwartete jährliche Wartungskosten in €',
            'neu_laufende_kosten': 'Weitere laufende Kosten pro Jahr in € (z.B. Gateway-Kosten)',
        }


class Step4LimasForm(forms.ModelForm):
    """
    Schritt 4: Lichtmanagementsystem (LMS) Konfiguration
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'lms_aktiviert',
            'lms_grundkosten',
            'lms_aufpreis_pro_leuchte',
        ]
        widgets = {
            'lms_aktiviert': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'lms_aktiviert'}),
            'lms_grundkosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'lms_aufpreis_pro_leuchte': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'lms_aktiviert': 'Aktivieren Sie diese Option, um LMS zu verwenden',
            'lms_grundkosten': 'Einmalige Grundkosten für LMS-System in €',
            'lms_aufpreis_pro_leuchte': 'Zusätzlicher Preis pro LMS-fähiger Leuchte in €',
        }


class Step4MotionSensorForm(forms.ModelForm):
    """
    Schritt 4a: Bewegungsmelder Konfiguration
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'bewegungsmelder_aktiviert',
            'bewegungsmelder_anzahl',
            'bewegungsmelder_abwesenheit_niveau',
            'bewegungsmelder_anwesenheit_niveau',
            'bewegungsmelder_frequentierung_stunden',
            'bewegungsmelder_frequentierung_minuten',
            'bewegungsmelder_mehrkosten',
            'bewegungsmelder_fadein',
            'bewegungsmelder_fadeout',
        ]
        widgets = {
            'bewegungsmelder_aktiviert': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'bewegungsmelder_aktiviert'}),
            'bewegungsmelder_anzahl': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'bewegungsmelder_abwesenheit_niveau': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'bewegungsmelder_anwesenheit_niveau': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'bewegungsmelder_frequentierung_stunden': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0'}),
            'bewegungsmelder_frequentierung_minuten': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '59'}),
            'bewegungsmelder_mehrkosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'bewegungsmelder_fadein': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '60'}),
            'bewegungsmelder_fadeout': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '60'}),
        }
        help_texts = {
            'bewegungsmelder_anzahl': 'Anzahl der Leuchten mit Bewegungsmelder',
            'bewegungsmelder_abwesenheit_niveau': 'Beleuchtungsniveau bei Abwesenheit in %',
            'bewegungsmelder_anwesenheit_niveau': 'Beleuchtungsniveau bei Anwesenheit in %',
            'bewegungsmelder_frequentierung_stunden': 'Durchschnittliche Anwesenheit in Stunden pro Tag',
            'bewegungsmelder_mehrkosten': 'Zusätzliche Kosten für Bewegungsmelder in €',
        }


class Step4DaylightForm(forms.ModelForm):
    """
    Schritt 4b: Tageslichtabhängige Regelung
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'tageslicht_aktiviert',
            'tageslicht_anzahl',
            'tageslicht_reduzierung_niveau',
            'tageslicht_nutzung_stunden',
            'tageslicht_nutzung_minuten',
            'tageslicht_mehrkosten',
        ]
        widgets = {
            'tageslicht_aktiviert': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'tageslicht_aktiviert'}),
            'tageslicht_anzahl': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'tageslicht_reduzierung_niveau': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'tageslicht_nutzung_stunden': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0'}),
            'tageslicht_nutzung_minuten': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '59'}),
            'tageslicht_mehrkosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'tageslicht_anzahl': 'Anzahl der Leuchten mit Tageslichtregelung',
            'tageslicht_reduzierung_niveau': 'Beleuchtungsniveau bei Tageslicht in %',
            'tageslicht_nutzung_stunden': 'Durchschnittliche Tageslichtnutzung in Stunden pro Tag',
            'tageslicht_mehrkosten': 'Zusätzliche Kosten für Tageslichtregelung in €',
        }


class Step4CalendarForm(forms.ModelForm):
    """
    Schritt 4c: Kalendersteuerung
    """
    class Meta:
        model = LightingCalculation
        fields = [
            'kalender_aktiviert',
            'kalender_anzahl_ausschalttage',
        ]
        widgets = {
            'kalender_aktiviert': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'kalender_aktiviert'}),
            'kalender_anzahl_ausschalttage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '365'}),
        }
        help_texts = {
            'kalender_aktiviert': 'Aktivieren für automatische Abschaltung an Feiertagen/Betriebsferien',
            'kalender_anzahl_ausschalttage': 'Anzahl der Tage mit Abschaltung (Feiertage, Betriebsferien)',
        }
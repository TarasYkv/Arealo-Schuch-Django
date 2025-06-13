from django import forms
from .models import Calculation

class CalculationForm(forms.ModelForm):
    class Meta:
        model = Calculation
        # Wir wählen hier nur die wichtigsten Eingabefelder für den Anfang aus.
        # Später können wir weitere Felder hinzufügen.
        fields = [
            'projektname',
            'strompreis',
            'neue_anlage_exists',
            # Felder für die Altanlage
            'alt_leistung',
            'alt_anzahl',
            'alt_h_pro_t',
            'alt_t_pro_j',
            # Felder für die Neuanlage
            'neu_leistung',
            'neu_anzahl',
            'neu_h_pro_t',
            'neu_t_pro_j',
            'neu_anschaffungskosten',
        ]
        # Hier können wir die deutschen Bezeichnungen für die Formularfelder festlegen
        labels = {
            'projektname': 'Projektname',
            'strompreis': 'Strompreis (€/kWh)',
            'neue_anlage_exists': 'Gibt es eine Bestandsanlage zum Vergleich?',
            'alt_leistung': 'Leistung je Leuchte der Altanlage (Watt)',
            'alt_anzahl': 'Anzahl Leuchten der Altanlage',
            'alt_h_pro_t': 'Betriebsstunden pro Tag (Altanlage)',
            'alt_t_pro_j': 'Betriebstage pro Jahr (Altanlage)',
            'neu_leistung': 'Leistung je Leuchte der Neuanlage (Watt)',
            'neu_anzahl': 'Anzahl Leuchten der Neuanlage',
            'neu_h_pro_t': 'Betriebsstunden pro Tag (Neuanlage)',
            'neu_t_pro_j': 'Betriebstage pro Jahr (Neuanlage)',
            'neu_anschaffungskosten': 'Anschaffungskosten Neuanlage (€)',
        }
# Kompletter Inhalt für: sportplatzApp/forms.py

from django import forms
from .models import Projekt

# ... (BELEUCHTUNGSKLASSEN_AUSWAHL und JA_NEIN_AUSWAHL bleiben unverändert) ...
BELEUCHTUNGSKLASSEN_AUSWAHL = [
    ('', '---------'),
    ('I', 'Beleuchtungsklasse I'),
    ('II', 'Beleuchtungsklasse II'),
    ('III', 'Beleuchtungsklasse III (75 lx)'),
    ('TRAINING', 'Trainingsbeleuchtung (30 lx)'),
]
JA_NEIN_AUSWAHL = ((True, 'Ja'), (False, 'Nein'))


class ProjektForm(forms.ModelForm):
    # Die Felder bleiben die gleichen wie vorher
    gewuenschte_beleuchtungsklasse = forms.ChoiceField(choices=BELEUCHTUNGSKLASSEN_AUSWAHL,
                                                       label="Gewünschte Beleuchtungsklasse")
    anzahl_maste = forms.IntegerField(label="Anzahl der Maste", initial=6)
    masthoehe = forms.FloatField(label="Masthöhe in Meter", initial=16)
    mastabstand = forms.FloatField(label="Mastabstand zu Spielfeld in Meter", initial=3)
    vorschaltgeraet_in_leuchte = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                        coerce=lambda x: x == 'True',
                                                        label="Vorschaltgerät integriert in der Leuchte", initial=True)
    vorschaltgeraet_im_mast = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                     coerce=lambda x: x == 'True',
                                                     label="Vorschaltgerät Einbau im Mast", initial=False)
    anzahl_masttueren = forms.IntegerField(label="Anzahl der Masttüren", initial=1)
    vorschaltgeraet_anbau = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                   coerce=lambda x: x == 'True', label="Vorschaltgerät Anbau",
                                                   initial=False)
    ist_schaltung_alle_zusammen = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                         coerce=lambda x: x == 'True',
                                                         label="IST: Schaltung alle Leuchten zusammen", initial=False)
    ist_schaltung_je_mast = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                   coerce=lambda x: x == 'True', label="IST: Schaltung je Mast",
                                                   initial=False)
    ist_schaltung_je_leuchte = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                      coerce=lambda x: x == 'True',
                                                      label="IST: Schaltung jede Leuchte einzeln", initial=False)
    wunsch_schaltung_je_mast = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                      coerce=lambda x: x == 'True', label="Wunsch: Schaltung je Mast",
                                                      initial=False)
    wunsch_schaltung_je_leuchte = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                         coerce=lambda x: x == 'True',
                                                         label="Wunsch: Schaltung jede Leuchte einzeln", initial=False)
    wunsch_dimmbar = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                            coerce=lambda x: x == 'True', label="Wunsch: Dimmbar (Dali)", initial=False)
    wunsch_steuerung_per_app = forms.TypedChoiceField(choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect,
                                                      coerce=lambda x: x == 'True',
                                                      label="Wunsch: Steuerung über Limas AIR", initial=True)

    class Meta:
        model = Projekt
        fields = ['projekt_name', 'projektort', 'kunde', 'ansprechpartner_email', 'laenge', 'breite']

        # HIER KOMMT DIE NEUE ANPASSUNG:
        # Wir weisen den Formularfeldern CSS-Klassen von Bootstrap zu.
        widgets = {
            'projekt_name': forms.TextInput(attrs={'class': 'form-control'}),
            'projektort': forms.TextInput(attrs={'class': 'form-control'}),
            'kunde': forms.TextInput(attrs={'class': 'form-control'}),
            'ansprechpartner_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'laenge': forms.NumberInput(attrs={'class': 'form-control'}),
            'breite': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hier weisen wir den Feldern, die nicht aus dem Modell kommen, die CSS-Klassen zu.
        self.fields['gewuenschte_beleuchtungsklasse'].widget.attrs.update({'class': 'form-select'})
        self.fields['anzahl_maste'].widget.attrs.update({'class': 'form-control'})
        self.fields['masthoehe'].widget.attrs.update({'class': 'form-control'})
        self.fields['mastabstand'].widget.attrs.update({'class': 'form-control'})
        self.fields['anzahl_masttueren'].widget.attrs.update({'class': 'form-control'})
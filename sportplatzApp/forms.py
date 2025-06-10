# Kompletter, finaler Inhalt für: sportplatzApp/forms.py

from django import forms
from .models import Projekt

# Auswahlmöglichkeiten zentral definieren
BELEUCHTUNGSKLASSEN_AUSWAHL = [
    ('', '---------'),
    ('I', 'Beleuchtungsklasse I'),
    ('II', 'Beleuchtungsklasse II'),
    ('III', 'Beleuchtungsklasse III (75 lx)'),
    ('TRAINING', 'Trainingsbeleuchtung (30 lx)'),
]
JA_NEIN_AUSWAHL = ((True, 'Ja'), (False, 'Nein'))


class ProjektForm(forms.ModelForm):
    # ======================================================================
    # ALLE FELDER AUS DEINER BESTANDSAUFNAHME-TABELLE
    # ======================================================================

    # --- Gewünschte Beleuchtungsklasse ---
    gewuenschte_beleuchtungsklasse = forms.ChoiceField(
        choices=BELEUCHTUNGSKLASSEN_AUSWAHL,
        label="Gewünschte Beleuchtungsklasse",
        required=True
    )
    anzahl_maste = forms.IntegerField(label="Anzahl der Maste", initial=6, required=True)
    masthoehe = forms.FloatField(label="Masthöhe in Meter", initial=16, required=True)
    mastabstand = forms.FloatField(label="Mastabstand zu Spielfeld in Meter", initial=3, required=True)

    # --- Vorschaltgerät ---
    vorschaltgeraet_in_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät integriert in der Leuchte",
        initial=True,  # Standard für Variante 1, 2, 3
        required=True
    )
    vorschaltgeraet_im_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Einbau im Mast",
        initial=False,
        required=True
    )
    anzahl_masttueren = forms.IntegerField(label="Anzahl der Masttüren", initial=1, required=True)
    vorschaltgeraet_anbau = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Anbau",
        initial=False,
        required=True
    )

    # --- IST-Zustand Schaltung ---
    ist_schaltung_alle_zusammen = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung alle Leuchten zusammen",
        initial=False,
        required=True
    )
    ist_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung je Mast",
        initial=False,
        required=True
    )
    ist_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung jede Leuchte einzeln",
        initial=False,
        required=True
    )

    # --- Wunsch-Schaltung ---
    wunsch_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung je Mast",
        initial=False,
        required=True
    )
    wunsch_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung jede Leuchte einzeln",
        initial=False,
        required=True
    )
    wunsch_dimmbar = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Dimmbar (Dali)",
        initial=False,  # Standard für Variante 3 ist "Nein"
        required=True
    )
    wunsch_steuerung_per_app = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Steuerung über Limas AIR",
        initial=True,  # Standard für Variante 3 ist "Ja"
        required=True
    )

    class Meta:
        model = Projekt
        # In 'fields' stehen nur die Felder, die direkt im Projekt-Modell gespeichert werden.
        fields = ['projekt_name', 'projektort', 'kunde', 'ansprechpartner_email', 'laenge', 'breite']
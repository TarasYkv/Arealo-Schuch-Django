# Kompletter, finaler Inhalt für: sportplatzApp/forms.py

from django import forms
from .models import Projekt

# Wir definieren die Auswahlmöglichkeiten einmal zentral für die Wiederverwendung.
BELEUCHTUNGSKLASSEN_AUSWAHL = [
    ('', '---------'),  # Leere Option
    ('I', 'Beleuchtungsklasse I'),
    ('II', 'Beleuchtungsklasse II'),
    ('III', 'Beleuchtungsklasse III (75 lx)'),
    ('TRAINING', 'Trainingsbeleuchtung (30 lx)'),
]
# Für Ja/Nein-Fragen, die als Radio-Buttons dargestellt werden sollen.
JA_NEIN_AUSWAHL = ((True, 'Ja'), (False, 'Nein'))


class ProjektForm(forms.ModelForm):
    # ======================================================================
    # HIER KOMMEN ALLE FELDER AUS DEINER TABELLE HIN
    # Diese Felder existieren nur im Formular, um die Logik zu steuern.
    # Sie werden nicht direkt im Projekt-Modell gespeichert.
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
        label="Vorschaltgerät integriert in der Leuchte", required=True
    )
    vorschaltgeraet_im_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Einbau im Mast", required=True
    )
    anzahl_masttueren = forms.IntegerField(label="Anzahl der Masttüren", initial=1, required=True)
    vorschaltgeraet_anbau = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Anbau", required=True
    )

    # --- IST-Zustand Schaltung ---
    ist_schaltung_alle_zusammen = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung alle Leuchten zusammen", required=True
    )
    ist_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung je Mast", required=True
    )
    ist_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung jede Leuchte einzeln", required=True
    )

    # --- Wunsch-Schaltung ---
    wunsch_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung je Mast", required=True
    )
    wunsch_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung jede Leuchte einzeln", required=True
    )
    wunsch_dimmbar = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Dimmbar (Dali)", required=True
    )
    wunsch_steuerung_per_app = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Steuerung über Limas AIR", required=True
    )

    class Meta:
        model = Projekt
        # In 'fields' stehen nur die Felder, die im Projekt-Modell gespeichert werden.
        fields = ['projekt_name', 'projektort', 'kunde', 'ansprechpartner_email', 'laenge', 'breite']
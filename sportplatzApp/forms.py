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
        label="Gewünschte Beleuchtungsklasse"
    )
    anzahl_maste = forms.IntegerField(label="Anzahl der Maste", initial=6)
    masthoehe = forms.FloatField(label="Masthöhe in Meter", initial=16)
    mastabstand = forms.FloatField(label="Mastabstand zu Spielfeld in Meter", initial=3)

    # --- Vorschaltgerät ---
    vorschaltgeraet_in_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät integriert in der Leuchte"
    )
    vorschaltgeraet_im_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Einbau im Mast"
    )
    anzahl_masttueren = forms.IntegerField(label="Anzahl der Masttüren", initial=1)
    vorschaltgeraet_anbau = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Vorschaltgerät Anbau"
    )

    # --- IST-Zustand Schaltung ---
    ist_schaltung_alle_zusammen = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung alle Leuchten zusammen"
    )
    ist_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung je Mast"
    )
    ist_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="IST: Schaltung jede Leuchte einzeln"
    )

    # --- Wunsch-Schaltung ---
    wunsch_schaltung_je_mast = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung je Mast"
    )
    wunsch_schaltung_je_leuchte = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Schaltung jede Leuchte einzeln"
    )
    wunsch_dimmbar = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Dimmbar (Dali)"
    )
    wunsch_steuerung_per_app = forms.TypedChoiceField(
        choices=JA_NEIN_AUSWAHL, widget=forms.RadioSelect, coerce=lambda x: x == 'True',
        label="Wunsch: Steuerung über Limas AIR"
    )

    class Meta:
        model = Projekt
        # In 'fields' stehen nur die Felder, die im Projekt-Modell gespeichert werden.
        fields = ['projekt_name', 'projektort', 'kunde', 'ansprechpartner_email', 'laenge', 'breite']
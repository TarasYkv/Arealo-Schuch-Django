from django.contrib import admin
from .models import LightingCalculation


@admin.register(LightingCalculation)
class LightingCalculationAdmin(admin.ModelAdmin):
    """
    Admin-Konfiguration für Beleuchtungsberechnungen
    """

    # Listenansicht
    list_display = [
        'projektname',
        'firmenname',
        'created_at',
        'user',
        'anlagen_typ',
        'neue_anlage_vorhanden',
        'lms_aktiviert',
        'formatted_ersparnis',
        'formatted_amortisation',
    ]

    list_filter = [
        'created_at',
        'anlagen_typ',
        'neue_anlage_vorhanden',
        'lms_aktiviert',
        'bewegungsmelder_aktiviert',
        'tageslicht_aktiviert',
        'kalender_aktiviert',
    ]

    search_fields = [
        'projektname',
        'firmenname',
        'kontakt_name',
        'kontakt_email',
        'user__username',
        'user__email',
    ]

    date_hierarchy = 'created_at'

    # Detailansicht
    fieldsets = (
        ('Projektinformationen', {
            'fields': (
                'user',
                'firmenname',
                'projektname',
                'strompreis',
                'anlagen_typ',
                'neue_anlage_vorhanden',
            )
        }),
        ('Kontaktdaten', {
            'fields': (
                'kontakt_name',
                'kontakt_email',
                'kontakt_telefon',
            ),
            'classes': ('collapse',),
        }),
        ('Bestandsanlage', {
            'fields': (
                'alt_hersteller',
                'alt_modell',
                'alt_leistung',
                'alt_anzahl',
                'alt_stunden_pro_tag',
                'alt_tage_pro_jahr',
                'alt_wartungskosten',
                'alt_laufende_kosten',
            ),
            'classes': ('collapse',),
        }),
        ('Neue Anlage', {
            'fields': (
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
            ),
            'classes': ('collapse',),
        }),
        ('Lichtmanagementsystem', {
            'fields': (
                'lms_aktiviert',
                'lms_grundkosten',
                'lms_aufpreis_pro_leuchte',
            ),
            'classes': ('collapse',),
        }),
        ('Bewegungsmelder', {
            'fields': (
                'bewegungsmelder_aktiviert',
                'bewegungsmelder_anzahl',
                'bewegungsmelder_abwesenheit_niveau',
                'bewegungsmelder_anwesenheit_niveau',
                'bewegungsmelder_frequentierung_stunden',
                'bewegungsmelder_frequentierung_minuten',
                'bewegungsmelder_mehrkosten',
                'bewegungsmelder_fadein',
                'bewegungsmelder_fadeout',
            ),
            'classes': ('collapse',),
        }),
        ('Tageslichtregelung', {
            'fields': (
                'tageslicht_aktiviert',
                'tageslicht_anzahl',
                'tageslicht_reduzierung_niveau',
                'tageslicht_nutzung_stunden',
                'tageslicht_nutzung_minuten',
                'tageslicht_mehrkosten',
            ),
            'classes': ('collapse',),
        }),
        ('Kalendersteuerung', {
            'fields': (
                'kalender_aktiviert',
                'kalender_anzahl_ausschalttage',
            ),
            'classes': ('collapse',),
        }),
        ('Berechnete Ergebnisse', {
            'fields': (
                'verbrauch_alt_kwh_jahr',
                'kosten_alt_jahr',
                'verbrauch_neu_ohne_lms_kwh_jahr',
                'kosten_neu_ohne_lms_jahr',
                'verbrauch_neu_mit_lms_kwh_jahr',
                'kosten_neu_mit_lms_jahr',
                'ersparnis_neu_zu_alt_jahr',
                'ersparnis_lms_jahr',
                'investitionskosten_gesamt',
                'investitionskosten_lms',
                'amortisation_neu_jahre',
                'amortisation_neu_monate',
                'amortisation_lms_jahre',
                'amortisation_lms_monate',
                'co2_emission_alt_kg_jahr',
                'co2_emission_neu_ohne_lms_kg_jahr',
                'co2_emission_neu_mit_lms_kg_jahr',
                'co2_ersparnis_kg_jahr',
            ),
            'classes': ('collapse',),
        }),
        ('Metadaten', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = [
        'created_at',
        'updated_at',
        'verbrauch_alt_kwh_jahr',
        'kosten_alt_jahr',
        'verbrauch_neu_ohne_lms_kwh_jahr',
        'kosten_neu_ohne_lms_jahr',
        'verbrauch_neu_mit_lms_kwh_jahr',
        'kosten_neu_mit_lms_jahr',
        'ersparnis_neu_zu_alt_jahr',
        'ersparnis_lms_jahr',
        'investitionskosten_gesamt',
        'investitionskosten_lms',
        'amortisation_neu_jahre',
        'amortisation_neu_monate',
        'amortisation_lms_jahre',
        'amortisation_lms_monate',
        'co2_emission_alt_kg_jahr',
        'co2_emission_neu_ohne_lms_kg_jahr',
        'co2_emission_neu_mit_lms_kg_jahr',
        'co2_ersparnis_kg_jahr',
    ]

    # Custom-Methoden für Listenansicht
    def formatted_ersparnis(self, obj):
        """Formatierte Ersparnis pro Jahr"""
        if obj.ersparnis_neu_zu_alt_jahr and obj.ersparnis_lms_jahr:
            total = obj.ersparnis_neu_zu_alt_jahr + obj.ersparnis_lms_jahr
            return f"{total:,.2f} €/Jahr"
        elif obj.ersparnis_neu_zu_alt_jahr:
            return f"{obj.ersparnis_neu_zu_alt_jahr:,.2f} €/Jahr"
        return "-"
    formatted_ersparnis.short_description = "Gesamtersparnis"

    def formatted_amortisation(self, obj):
        """Formatierte Amortisationszeit"""
        if obj.amortisation_neu_jahre:
            jahre = int(obj.amortisation_neu_jahre)
            monate = int((obj.amortisation_neu_jahre - jahre) * 12)
            if monate > 0:
                return f"{jahre} Jahre, {monate} Monate"
            return f"{jahre} Jahre"
        return "-"
    formatted_amortisation.short_description = "Amortisation"

    # Aktionen
    actions = ['recalculate_selected']

    def recalculate_selected(self, request, queryset):
        """Neuberechnung für ausgewählte Einträge"""
        for calculation in queryset:
            calculation.save()  # Löst die Neuberechnung aus
        self.message_user(request, f"{queryset.count()} Berechnungen wurden aktualisiert.")
    recalculate_selected.short_description = "Ausgewählte Berechnungen neu berechnen"
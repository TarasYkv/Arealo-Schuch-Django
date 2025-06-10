from django.db import models

class Calculation(models.Model):
    # Tab 1: General Info
    projektname = models.CharField(max_length=200, default="My Project")
    strompreis = models.FloatField(default=0.30)
    # ... add other fields from Tab 1 like firmenname, name, email, etc.

    # Tab 2: Old System (Bestandsanlage)
    neue_anlage_exists = models.BooleanField(default=True)
    alt_hersteller = models.CharField(max_length=100, blank=True)
    alt_leistung = models.FloatField(default=0)
    alt_anzahl = models.IntegerField(default=0)
    alt_h_pro_t = models.FloatField(default=0) # althProT
    alt_t_pro_j = models.IntegerField(default=0) # alttProJ
    # ... etc for all 'alt' fields

    # Tab 2: New System (Neue Anlage)
    neu_hersteller = models.CharField(max_length=100, default="Schuch")
    neu_leistung = models.FloatField(default=0)
    neu_anzahl = models.IntegerField(default=0)
    neu_h_pro_t = models.FloatField(default=0) # neuhProT
    neu_t_pro_j = models.IntegerField(default=0) # neutProJ
    neu_anschaffungskosten = models.FloatField(default=0)
    # ... etc for all 'neu' fields

    # Tab 3: Light Management System (LMS)
    bewegungsmelder = models.BooleanField(default=False)
    abwesenheitswert = models.IntegerField(default=20) # Abscence value %
    anwesenheitswert = models.IntegerField(default=100) # Presence value %
    frequentierung_stunden = models.FloatField(default=4.0) # Hours of frequent use
    tageslicht = models.BooleanField(default=False)
    reduzierungs_niveau = models.FloatField(default=40) # Reduction level %
    # ... etc for all LMS fields

    # --- Calculated Results ---
    # You can store the results in the model as well
    amortisationszeitraum_in_jahren = models.FloatField(null=True, blank=True)
    ersparnis_alt_neu = models.FloatField(null=True, blank=True)
    gesamtkosten_mit_lms = models.FloatField(null=True, blank=True)
    # ... add all other result fields

    def __str__(self):
        return self.projektname
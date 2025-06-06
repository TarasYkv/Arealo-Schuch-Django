# in sportplatzApp/models.py
# (Die Modelle Komponente und Projekt bleiben unverändert)

class Variante(models.Model):
    name = models.CharField(max_length=200, verbose_name="Name der Variante")
    beschreibung = models.CharField(max_length=300, verbose_name="Beschreibung")

    # --- Leuchten ---
    anzahl_leuchten = models.IntegerField(default=16)
    leuchte = models.ForeignKey(Komponente, on_delete=models.PROTECT, related_name="leuchte_in_varianten",
                                limit_choices_to={'kategorie': 'LEUCHTE'})
    # Preis für alle Leuchten - NEU
    preis_leuchten = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Preis für alle Leuchten")

    # --- Traverse ---
    anzahl_traversen = models.IntegerField(default=6)
    traverse = models.ForeignKey(Komponente, on_delete=models.PROTECT, related_name="traverse_in_varianten",
                                 limit_choices_to={'kategorie': 'TRAVERSE'})
    # Preis für alle Traversen - NEU
    preis_traversen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                          verbose_name="Preis für alle Traversen")

    # --- Externe EVGs ---
    anzahl_externe_evgs = models.IntegerField(default=0)
    externes_evg = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="evg_in_varianten", limit_choices_to={'kategorie': 'EVG'})
    # Preis für alle externen EVGs - NEU
    preis_externe_evgs = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             verbose_name="Preis für alle externen EVGs")

    # --- Verteilerboxen ---
    anzahl_verteilerboxen = models.IntegerField(default=0)
    verteilerbox = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="verteilerbox_in_varianten",
                                     limit_choices_to={'kategorie': 'VERTEILERBOX'})
    # Preis für alle Verteilerboxen - NEU
    preis_verteilerboxen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                               verbose_name="Preis für alle Verteilerboxen")

    # --- Steuerboxen ---
    anzahl_steuerboxen = models.IntegerField(default=0)
    steuerbox = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="steuerbox_in_varianten", limit_choices_to={'kategorie': 'STEUERBOX'})
    # Preis für alle Steuerboxen - NEU
    preis_steuerboxen = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                            verbose_name="Preis für alle Steuerboxen")

    # --- Steuerbausteine ---
    anzahl_steuerbausteine = models.IntegerField(default=0)
    steuerbaustein = models.ForeignKey(Komponente, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="steuerbaustein_in_varianten",
                                       limit_choices_to={'kategorie': 'STEUERBAUSTEIN'})
    # Preis für alle Steuerbausteine - NEU
    preis_steuerbausteine = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                verbose_name="Preis für alle Steuerbausteine")

    # --- Bemerkung & Gesamtpreis ---
    bemerkung_konfiguration = models.TextField(blank=True)
    # Preis für die gesamte Variante - NEU
    preis_gesamt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       verbose_name="Preis für die gesamte Variante")

    def __str__(self):
        return self.name
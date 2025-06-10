# Kompletter Inhalt für die EINE Migrationsdatei: 0001_initial.py

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

# ======================================================================
# UNSER SKRIPT ZUM BEFÜLLEN DER DATEN
# ======================================================================
def create_initial_data(apps, schema_editor):
    Komponente = apps.get_model('sportplatzApp', 'Komponente')
    Variante = apps.get_model('sportplatzApp', 'Variante')
    print("\nErstelle Komponenten...")
    leuchte_op = Komponente.objects.create(name="7950 14404SP OP", kategorie="LEUCHTE")
    leuchte_dimd_op = Komponente.objects.create(name="7950 14404SP DIMD OP", kategorie="LEUCHTE")
    leuchte_op_pfld = Komponente.objects.create(name="7950 14404SP OP PFLD", kategorie="LEUCHTE")
    leuchte_ov = Komponente.objects.create(name="7950 14404SP OV", kategorie="LEUCHTE")
    traverse_standard = Komponente.objects.create(name="TR 900/108/170/4 M10/12", kategorie="TRAVERSE")
    evg_900w = Komponente.objects.create(name="900W", kategorie="EVG")
    evg_1200w = Komponente.objects.create(name="1200W", kategorie="EVG")
    vbox_tr = Komponente.objects.create(name="6VBOX TR", kategorie="VERTEILERBOX")
    steuerbox_vbox_dfl_tr = Komponente.objects.create(name="VBOX DFL TR", kategorie="STEUERBOX")
    steuerbox_vbox_rfl_tr = Komponente.objects.create(name="VBOX RFL TR", kategorie="STEUERBOX")
    steuerbaustein_rfl_hub = Komponente.objects.create(name="RFL LIMAS Air HUB TRI", kategorie="STEUERBAUSTEIN")
    print("Alle Komponenten erfolgreich erstellt.")
    print("Erstelle Varianten...")
    Variante.objects.create(name="Variante 1", beschreibung="ON/OFF-Leuchten; Leuchten mit eingebauten EVGs; ohne Steuerung", anzahl_leuchten=16, leuchte=leuchte_op, preis_leuchten=10000.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00, bemerkung_konfiguration="Günstigste Konfiguration;", preis_gesamt=14200.00)
    Variante.objects.create(name="Variante 2", beschreibung="DALI-Leuchten; Leuchten mit eingebauten EVGs; mit DALI-Steuerung", anzahl_leuchten=16, leuchte=leuchte_dimd_op, preis_leuchten=11000.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00, bemerkung_konfiguration="Kabelgebundene Steuerung DALI;", preis_gesamt=15200.00)
    Variante.objects.create(name="Variante 3", beschreibung="PFL-Leuchten; Leuchten mit eingebauten EVGs; mit Funksteuerung LIMAS Air", anzahl_leuchten=16, leuchte=leuchte_op_pfld, preis_leuchten=11500.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00, anzahl_steuerbausteine=16, steuerbaustein=steuerbaustein_rfl_hub, preis_steuerbausteine=2500.00, bemerkung_konfiguration="Funksteuerung LIMAS Air; Jede einzelne Leuchte ist steuerbar", preis_gesamt=18200.00)
    Variante.objects.create(name="Variante 4", beschreibung="OV-Leuchten; Leuchten ohne EVGs; ohne Steuerung", anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9000.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00, anzahl_verteilerboxen=4, verteilerbox=vbox_tr, preis_verteilerboxen=800.00, bemerkung_konfiguration="Günstigste Konfiguration mit externe EVGs;", preis_gesamt=14600.00)
    Variante.objects.create(name="Variante 5", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Kabelgebundener Steuerung", anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9000.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00, anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00, bemerkung_konfiguration="Kabelgebundene Steuerung mit externe EVGs;", preis_gesamt=15000.00)
    Variante.objects.create(name="Variante 6", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air", anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9500.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00, anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_dfl_tr, preis_steuerboxen=1800.00, anzahl_steuerbausteine=8, steuerbaustein=steuerbaustein_rfl_hub, preis_steuerbausteine=1300.00, bemerkung_konfiguration="Funksteuerung mit externe EVGs; immer 2 Leuchten sind gemeinsam steuerbar;", preis_gesamt=17400.00)
    Variante.objects.create(name="Variante 7", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air", anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=12000.00, anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00, anzahl_externe_evgs=8, externes_evg=evg_1200w, preis_externe_evgs=2200.00, anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_rfl_tr, preis_steuerboxen=2000.00, bemerkung_konfiguration="Funksteuerung mit externe EVGs; Jede Leuchte ist einzeln steuerbar;", preis_gesamt=19200.00)
    print("Alle 7 Varianten erfolgreich erstellt.")
# ======================================================================

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Komponente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name der Komponente')),
                ('kategorie', models.CharField(choices=[('LEUCHTE', 'Leuchte'), ('TRAVERSE', 'Traverse'), ('EVG', 'Externes EVG'), ('VERTEILERBOX', 'Verteilerbox'), ('STEUERBOX', 'Steuerbox'), ('STEUERBAUSTEIN', 'Steuerbaustein'), ('SONSTIGES', 'Sonstiges')], max_length=100, verbose_name='Kategorie')),
                ('beschreibung', models.TextField(blank=True, verbose_name='Beschreibung')),
            ],
        ),
        migrations.CreateModel(
            name='Variante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name der Variante')),
                ('beschreibung', models.CharField(max_length=300, verbose_name='Beschreibung')),
                ('preis_leuchten', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle Leuchten')),
                ('preis_traversen', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle Traversen')),
                ('preis_externe_evgs', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle externen EVGs')),
                ('preis_verteilerboxen', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle Verteilerboxen')),
                ('preis_steuerboxen', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle Steuerboxen')),
                ('preis_steuerbausteine', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für alle Steuerbausteine')),
                ('preis_gesamt', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preis für die gesamte Variante')),
                ('anzahl_leuchten', models.IntegerField(default=16)),
                ('anzahl_traversen', models.IntegerField(default=6)),
                ('anzahl_externe_evgs', models.IntegerField(default=0)),
                ('anzahl_verteilerboxen', models.IntegerField(default=0)),
                ('anzahl_steuerboxen', models.IntegerField(default=0)),
                ('anzahl_steuerbausteine', models.IntegerField(default=0)),
                ('bemerkung_konfiguration', models.TextField(blank=True)),
                ('externes_evg', models.ForeignKey(blank=True, limit_choices_to={'kategorie': 'EVG'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='evg_in_varianten', to='sportplatzApp.komponente')),
                ('leuchte', models.ForeignKey(limit_choices_to={'kategorie': 'LEUCHTE'}, on_delete=django.db.models.deletion.PROTECT, related_name='leuchte_in_varianten', to='sportplatzApp.komponente')),
                ('steuerbaustein', models.ForeignKey(blank=True, limit_choices_to={'kategorie': 'STEUERBAUSTEIN'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='steuerbaustein_in_varianten', to='sportplatzApp.komponente')),
                ('steuerbox', models.ForeignKey(blank=True, limit_choices_to={'kategorie': 'STEUERBOX'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='steuerbox_in_varianten', to='sportplatzApp.komponente')),
                ('traverse', models.ForeignKey(limit_choices_to={'kategorie': 'TRAVERSE'}, on_delete=django.db.models.deletion.PROTECT, related_name='traverse_in_varianten', to='sportplatzApp.komponente')),
                ('verteilerbox', models.ForeignKey(blank=True, limit_choices_to={'kategorie': 'VERTEILERBOX'}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='verteilerbox_in_varianten', to='sportplatzApp.komponente')),
            ],
        ),
        migrations.CreateModel(
            name='Projekt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('projekt_name', models.CharField(max_length=200, verbose_name='Projektname')),
                ('projektort', models.CharField(max_length=200, verbose_name='Projektort')),
                ('kunde', models.CharField(max_length=200, verbose_name='Kunde')),
                ('datum', models.DateField(default=django.utils.timezone.now, verbose_name='Datum')),
                ('ansprechpartner_email', models.EmailField(max_length=254, verbose_name='E-Mail des Ansprechpartners')),
                ('laenge', models.FloatField(default=105, verbose_name='Länge in Metern')),
                ('breite', models.FloatField(default=68, verbose_name='Breite in Metern')),
                ('erstellungsdatum', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('ausgewaehlte_variante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sportplatzApp.variante', verbose_name='Gewählte Konfigurations-Variante')),
            ],
        ),
        # ======================================================================
        # HIER WIRD UNSER DATEN-SKRIPT ZUR LISTE HINZUGEFÜGT
        # ======================================================================
        migrations.RunPython(create_initial_data),
    ]
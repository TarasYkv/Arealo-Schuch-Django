# Kompletter, finaler Inhalt für deine Daten-Migrations-Datei (z.B. 0002_populate_variants.py)

from django.db import migrations

def create_initial_data(apps, schema_editor):
    """
    Diese Funktion wird ausgeführt, wenn wir die Migration anwenden.
    Sie erstellt alle Komponenten und Varianten.
    """
    Komponente = apps.get_model('sportplatzApp', 'Komponente')
    Variante = apps.get_model('sportplatzApp', 'Variante')

    # === TEIL 1: Alle benötigten Komponenten anlegen ===
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

    # === TEIL 2: Alle 7 Varianten anlegen und mit Komponenten verknüpfen ===
    print("Erstelle Varianten...")

    Variante.objects.create(
        name="Variante 1", beschreibung="ON/OFF-Leuchten; Leuchten mit eingebauten EVGs; ohne Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_op, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr,
        bemerkung_konfiguration="Günstigste Konfiguration;"
    )
    Variante.objects.create(
        name="Variante 2", beschreibung="DALI-Leuchten; Leuchten mit eingebauten EVGs; mit DALI-Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_dimd_op, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr,
        bemerkung_konfiguration="Kabelgebundene Steuerung DALI;"
    )
    Variante.objects.create(
        name="Variante 3", beschreibung="PFL-Leuchten; Leuchten mit eingebauten EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_op_pfld, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr, anzahl_steuerbausteine=16, steuerbaustein=steuerbaustein_rfl_hub,
        bemerkung_konfiguration="Funksteuerung LIMAS Air; Jede einzelne Leuchte ist steuerbar"
    )
    Variante.objects.create(
        name="Variante 4", beschreibung="OV-Leuchten; Leuchten ohne EVGs; ohne Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_ov, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_externe_evgs=8, externes_evg=evg_900w, anzahl_verteilerboxen=4, verteilerbox=vbox_tr,
        bemerkung_konfiguration="Günstigste Konfiguration mit externe EVGs;"
    )
    Variante.objects.create(
        name="Variante 5", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Kabelgebundener Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_ov, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_externe_evgs=8, externes_evg=evg_900w, anzahl_verteilerboxen=6, verteilerbox=vbox_tr,
        bemerkung_konfiguration="Kabelgebundene Steuerung mit externe EVGs;"
    )
    Variante.objects.create(
        name="Variante 6", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_ov, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_externe_evgs=8, externes_evg=evg_900w, anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_dfl_tr,
        anzahl_steuerbausteine=8, steuerbaustein=steuerbaustein_rfl_hub,
        bemerkung_konfiguration="Funksteuerung mit externe EVGs; immer 2 Leuchten sind gemeinsam steuerbar;"
    )
    Variante.objects.create(
        name="Variante 7", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_ov, anzahl_traversen=6, traverse=traverse_standard,
        anzahl_externe_evgs=8, externes_evg=evg_1200w, anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_rfl_tr,
        bemerkung_konfiguration="Funksteuerung mit externe EVGs; Jede Leuchte ist einzeln steuerbar;"
    )
    print("Alle 7 Varianten erfolgreich erstellt.")


class Migration(migrations.Migration):

    dependencies = [
        # Stellt sicher, dass diese Migration nach der Erstellung der Tabellen läuft
        ('sportplatzApp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_data),
    ]
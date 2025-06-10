# Kompletter, finaler Inhalt für: sportplatzApp/migrations/0002_populate_variants.py

from django.db import migrations


def create_initial_data(apps, schema_editor):
    """
    Diese Funktion wird ausgeführt, wenn wir die Migration anwenden.
    Sie erstellt alle Komponenten und Varianten.
    """
    # Wir müssen die Modelle über apps.get_model holen, anstatt sie direkt zu importieren.
    # Das ist die Standardmethode in Daten-Migrationen.
    Komponente = apps.get_model('sportplatzApp', 'Komponente')
    Variante = apps.get_model('sportplatzApp', 'Variante')

    # === TEIL 1: Alle benötigten Komponenten anlegen ===
    print("\nErstelle Komponenten...")

    # Leuchten
    leuchte_op = Komponente.objects.create(name="7950 14404SP OP", kategorie="LEUCHTE")
    leuchte_dimd_op = Komponente.objects.create(name="7950 14404SP DIMD OP", kategorie="LEUCHTE")
    leuchte_op_pfld = Komponente.objects.create(name="7950 14404SP OP PFLD", kategorie="LEUCHTE")
    leuchte_ov = Komponente.objects.create(name="7950 14404SP OV", kategorie="LEUCHTE")

    # Traversen
    traverse_standard = Komponente.objects.create(name="TR 900/108/170/4 M10/12", kategorie="TRAVERSE")

    # Externe EVGs
    evg_900w = Komponente.objects.create(name="900W", kategorie="EVG")
    evg_1200w = Komponente.objects.create(name="1200W", kategorie="EVG")

    # Verteilerboxen
    vbox_tr = Komponente.objects.create(name="6VBOX TR", kategorie="VERTEILERBOX")

    # Steuerboxen
    steuerbox_vbox_dfl_tr = Komponente.objects.create(name="VBOX DFL TR", kategorie="STEUERBOX")
    steuerbox_vbox_rfl_tr = Komponente.objects.create(name="VBOX RFL TR", kategorie="STEUERBOX")

    # Steuerbausteine
    steuerbaustein_rfl_hub = Komponente.objects.create(name="RFL LIMAS Air HUB TRI", kategorie="STEUERBAUSTEIN")

    print("Alle Komponenten erfolgreich erstellt.")

    # === TEIL 2: Alle 7 Varianten anlegen und mit Komponenten verknüpfen ===
    print("Erstelle Varianten...")

    # Annahme für Beispiel-Preise
    # Du solltest diese Werte durch deine echten Preise ersetzen.
    Variante.objects.create(
        name="Variante 1", beschreibung="ON/OFF-Leuchten; Leuchten mit eingebauten EVGs; ohne Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_op, preis_leuchten=10000.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00,
        bemerkung_konfiguration="Günstigste Konfiguration;", preis_gesamt=14200.00
    )
    Variante.objects.create(
        name="Variante 2", beschreibung="DALI-Leuchten; Leuchten mit eingebauten EVGs; mit DALI-Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_dimd_op, preis_leuchten=11000.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00,
        bemerkung_konfiguration="Kabelgebundene Steuerung DALI;", preis_gesamt=15200.00
    )
    Variante.objects.create(
        name="Variante 3", beschreibung="PFL-Leuchten; Leuchten mit eingebauten EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_op_pfld, preis_leuchten=11500.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00,
        anzahl_steuerbausteine=16, steuerbaustein=steuerbaustein_rfl_hub, preis_steuerbausteine=2500.00,
        bemerkung_konfiguration="Funksteuerung LIMAS Air; Jede einzelne Leuchte ist steuerbar", preis_gesamt=18200.00
    )
    Variante.objects.create(
        name="Variante 4", beschreibung="OV-Leuchten; Leuchten ohne EVGs; ohne Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9000.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00,
        anzahl_verteilerboxen=4, verteilerbox=vbox_tr, preis_verteilerboxen=800.00,
        bemerkung_konfiguration="Günstigste Konfiguration mit externe EVGs;", preis_gesamt=14600.00
    )
    Variante.objects.create(
        name="Variante 5", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Kabelgebundener Steuerung",
        anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9000.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00,
        anzahl_verteilerboxen=6, verteilerbox=vbox_tr, preis_verteilerboxen=1200.00,
        bemerkung_konfiguration="Kabelgebundene Steuerung mit externe EVGs;", preis_gesamt=15000.00
    )
    Variante.objects.create(
        name="Variante 6", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=9500.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_externe_evgs=8, externes_evg=evg_900w, preis_externe_evgs=1800.00,
        anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_dfl_tr, preis_steuerboxen=1800.00,
        anzahl_steuerbausteine=8, steuerbaustein=steuerbaustein_rfl_hub, preis_steuerbausteine=1300.00,
        bemerkung_konfiguration="Funksteuerung mit externe EVGs; immer 2 Leuchten sind gemeinsam steuerbar;",
        preis_gesamt=17400.00
    )
    Variante.objects.create(
        name="Variante 7", beschreibung="OV-Leuchten; Leuchten ohne EVGs; mit Funksteuerung LIMAS Air",
        anzahl_leuchten=16, leuchte=leuchte_ov, preis_leuchten=12000.00,
        anzahl_traversen=6, traverse=traverse_standard, preis_traversen=3000.00,
        anzahl_externe_evgs=8, externes_evg=evg_1200w, preis_externe_evgs=2200.00,
        anzahl_steuerboxen=8, steuerbox=steuerbox_vbox_rfl_tr, preis_steuerboxen=2000.00,
        bemerkung_konfiguration="Funksteuerung mit externe EVGs; Jede Leuchte ist einzeln steuerbar;",
        preis_gesamt=19200.00
    )
    print("Alle 7 Varianten erfolgreich erstellt.")


class Migration(migrations.Migration):
    dependencies = [
        # Diese Zeile stellt sicher, dass diese Daten-Migration
        # NACH der Erstellung der Tabellen ausgeführt wird.
        ('sportplatzApp', '0001_initial'),
    ]

    operations = [
        # Diese Zeile weist Django an, die Funktion create_initial_data von oben auszuführen.
        migrations.RunPython(create_initial_data),
    ]
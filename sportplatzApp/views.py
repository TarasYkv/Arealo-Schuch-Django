# Kompletter, finaler Inhalt für: sportplatzApp/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from .forms import ProjektForm
from .models import Projekt, Variante, Komponente


# ==============================================================================
# DIE INTELLIGENZ DEINES TOOLS: DIE ENTSCHEIDUNGSFUNKTION
# ==============================================================================
def finde_passende_variante(form_data):
    """
    Diese Funktion enthält die Entscheidungsregeln, um basierend auf den
    Formulareingaben die beste Variante zu finden. Gibt 'None' zurück,
    wenn keine exakte Regel zutrifft.
    """
    try:
        # Hole alle relevanten Eingaben aus dem Formular
        ist_vg_im_mast = form_data.get('vorschaltgeraet_im_mast')
        ist_vg_anbau = form_data.get('vorschaltgeraet_anbau')
        hat_app_wunsch = form_data.get('wunsch_steuerung_per_app')
        hat_dimm_wunsch = form_data.get('wunsch_dimmbar')
        hat_einzelsteuerung_wunsch = form_data.get('wunsch_schaltung_je_leuchte')

        # === HAUPTENTSCHEIDUNG: INTERNES ODER EXTERNES VORSCHALTGERÄT? ===

        if ist_vg_im_mast or ist_vg_anbau:
            # --- FALL A: EXTERNES VORSCHALTGERÄT (OV-Leuchten -> Varianten 4, 5, 6, 7) ---
            print("LOGIK: Gehe in den Zweig 'Externes Vorschaltgerät'")

            if hat_app_wunsch and hat_einzelsteuerung_wunsch:
                return Variante.objects.get(name="Variante 7")
            elif hat_app_wunsch:
                return Variante.objects.get(name="Variante 6")
            else:
                # ANNAHME: Wir nehmen die günstigste Variante 4, wenn keine spezielle Steuerung gewünscht ist.
                # Hier könntest du noch zwischen Variante 4 und 5 unterscheiden.
                return Variante.objects.get(name="Variante 4")

        else:
            # --- FALL B: INTERNES/INTEGRIERTES VORSCHALTGERÄT (Varianten 1, 2, 3) ---
            print("LOGIK: Gehe in den Zweig 'Internes Vorschaltgerät'")

            if hat_app_wunsch:
                return Variante.objects.get(name="Variante 3")
            elif hat_dimm_wunsch:
                return Variante.objects.get(name="Variante 2")
            else:
                # Nur wenn keine speziellen Wünsche bestehen, wird die Standard-Variante gewählt
                if not hat_einzelsteuerung_wunsch and not hat_app_wunsch and not hat_dimm_wunsch:
                    return Variante.objects.get(name="Variante 1")

        # Wenn keine der obigen, spezifischen Regeln zutrifft, geben wir None zurück.
        print("LOGIK: Keine exakte Regel hat zugetroffen.")
        return None

    except Variante.DoesNotExist as e:
        # Dieser Fehler tritt auf, wenn eine Regel zutrifft, aber die
        # entsprechende Variante im Admin-Bereich nicht mit exaktem Namen existiert.
        print(f"WARNUNG: Erwartete Variante konnte nicht gefunden werden: {e}")
        return None


# ==============================================================================
# DIE HAUPT-VIEWS FÜR DIE WEBSEITEN
# ==============================================================================
def projekt_anlegen(request):
    if request.method == 'POST':
        form = ProjektForm(request.POST)
        if form.is_valid():
            form_data = form.cleaned_data

            # --- UNSERE SPIONE ---
            print("--- DEBUG-START ---")
            print("Empfangene Formulardaten:", form_data)

            passende_variante = finde_passende_variante(form_data)

            print("Von Logik ermittelte Variante:", passende_variante)
            print("--- DEBUG-ENDE ---")
            # ---

            if passende_variante:
                # ... (normaler Ablauf)
                neues_projekt = form.save(commit=False)
                neues_projekt.ausgewaehlte_variante = passende_variante
                neues_projekt.save()
                # ... (E-Mail Code) ...
                return redirect('danke_seite', projekt_id=neues_projekt.id)
            else:
                # Fall, wenn keine Variante gefunden wurde
                return redirect('keine_variante_gefunden')
    else:
        form = ProjektForm()

    return render(request, 'sportplatzApp/projekt_anlegen.html', {'form': form})


def danke_seite(request, projekt_id):
    """
    Diese View zeigt die Ergebnisseite mit der Zusammenfassung an.
    """
    projekt = get_object_or_404(Projekt, pk=projekt_id)
    context = {'projekt': projekt}
    return render(request, 'sportplatzApp/danke.html', context)


def keine_variante_gefunden(request):
    """
    Diese View zeigt die Seite an, wenn keine passende Konfiguration gefunden wurde.
    """
    return render(request, 'sportplatzApp/keine_variante_gefunden.html')
# Kompletter, finaler Inhalt für: sportplatzApp/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from .forms import ProjektForm
from .models import Projekt, Variante, Komponente


# *** NEU: Diese View-Funktion muss hinzugefügt werden ***
def sportplatz_start_view(request):
    """
    Rendert die Startseite des Sportplatz-Konfigurators.
    Diese View wird von der URL 'sportplatz_start' aufgerufen.
    """
    context = {
        'page_title': 'Sportplatz-Konfigurator: Startseite',
        # Optional: Fügen Sie hier Daten hinzu, die Sie an das Template übergeben möchten
    }
    return render(request, 'sportplatzApp/sportplatz_start.html', context)


# Die Funktion finde_passende_variante bleibt unverändert
def finde_passende_variante(form_data):
    try:
        ist_vg_im_mast = form_data.get('vorschaltgeraet_im_mast')
        ist_vg_anbau = form_data.get('vorschaltgeraet_anbau')
        hat_app_wunsch = form_data.get('wunsch_steuerung_per_app')
        hat_dimm_wunsch = form_data.get('wunsch_dimmbar')
        hat_einzelsteuerung_wunsch = form_data.get('wunsch_schaltung_je_leuchte')

        if ist_vg_im_mast or ist_vg_anbau:
            # Fall A: Externes Vorschaltgerät
            if hat_app_wunsch and hat_einzelsteuerung_wunsch:
                return Variante.objects.get(name="Variante 7")
            elif hat_app_wunsch:
                return Variante.objects.get(name="Variante 6")
            else:
                return Variante.objects.get(name="Variante 4")
        else:
            # Fall B: Internes Vorschaltgerät
            if hat_app_wunsch:
                return Variante.objects.get(name="Variante 3")
            elif hat_dimm_wunsch:
                return Variante.objects.get(name="Variante 2")
            else:
                if not hat_einzelsteuerung_wunsch:
                    return Variante.objects.get(name="Variante 1")
        return None
    except Variante.DoesNotExist:
        return None


def projekt_anlegen(request):
    if request.method == 'POST':
        form = ProjektForm(request.POST)
        if form.is_valid():
            form_data = form.cleaned_data
            passende_variante = finde_passende_variante(form_data)

            if passende_variante:
                neues_projekt = form.save(commit=False)
                neues_projekt.ausgewaehlte_variante = passende_variante
                neues_projekt.save()

                subject = f"Konfiguration für Ihr Projekt: {neues_projekt.projekt_name}"
                from_email = 'planungstool@taras-yuzkiv.de'
                recipient_list = [neues_projekt.ansprechpartner_email]

                admin_url = request.build_absolute_uri(
                    reverse('admin:sportplatzApp_projekt_change', args=(neues_projekt.id,))
                )

                varianten_details_html = f"""
                    <tr><th>Leuchtentyp</th><td>{passende_variante.leuchte.name} (Anzahl: {passende_variante.anzahl_leuchten})</td></tr>
                    <tr><th>Preis Leuchten</th><td>{passende_variante.preis_leuchten or 'N/A'} €</td></tr>
                    <tr><th>Traversentyp</th><td>{passende_variante.traverse.name} (Anzahl: {passende_variante.anzahl_traversen})</td></tr>
                    <tr><th>Preis Traversen</th><td>{passende_variante.preis_traversen or 'N/A'} €</td></tr>
                """
                if passende_variante.externes_evg:
                    varianten_details_html += f"<tr><th>Externes EVG</th><td>{passende_variante.externes_evg.name} (Anzahl: {passende_variante.anzahl_externe_evgs})</td></tr>"
                    varianten_details_html += f"<tr><th>Preis externe EVGs</th><td>{passende_variante.preis_externe_evgs or 'N/A'} €</td></tr>"
                if passende_variante.verteilerbox:
                    varianten_details_html += f"<tr><th>Verteilerbox</th><td>{passende_variante.verteilerbox.name} (Anzahl: {passende_variante.anzahl_verteilerboxen})</td></tr>"
                    varianten_details_html += f"<tr><th>Preis Verteilerboxen</th><td>{passende_variante.preis_verteilerboxen or 'N/A'} €</td></tr>"
                if passende_variante.steuerbox:
                    varianten_details_html += f"<tr><th>Steuerbox</th><td>{passende_variante.steuerbox.name} (Anzahl: {passende_variante.anzahl_steuerboxen})</td></tr>"
                    varianten_details_html += f"<tr><th>Preis Steuerboxen</th><td>{passende_variante.preis_steuerboxen or 'N/A'} €</td></tr>"
                if passende_variante.steuerbaustein:
                    varianten_details_html += f"<tr><th>Steuerbaustein</th><td>{passende_variante.steuerbaustein.name} (Anzahl: {passende_variante.anzahl_steuerbausteine})</td></tr>"
                    varianten_details_html += f"<tr><th>Preis Steuerbausteine</th><td>{passende_variante.preis_steuerbausteine or 'N/A'} €</td></tr>"
                if passende_variante.preis_gesamt:
                    varianten_details_html += f'<tr style="font-weight: bold;"><th>Preis für die gesamte Variante</th><td>{passende_variante.preis_gesamt} €</td></tr>'

                bestandsaufnahme_html = ""
                for field in form:
                    value = form.cleaned_data.get(field.name)
                    display_value = 'Ja' if value is True else 'Nein' if value is False else value
                    bestandsaufnahme_html += f"<tr><td>{field.label}</td><td>{display_value}</td></tr>"

                html_content = f"""
                <html>
                    <head>
                        <style>
                            body {{ font-family: sans-serif; color: #333; }}
                            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                            th {{ background-color: #f2f2f2; width: 40%; }}
                            h2, h3 {{ color: #004077; }}
                        </style>
                    </head>
                    <body>
                        <h2>Zusammenfassung für Ihr Projekt: {neues_projekt.projekt_name}</h2>
                        <p>Vielen Dank für Ihre Anfrage. Basierend auf Ihrer Bestandsaufnahme empfehlen wir die folgende Konfiguration.</p>

                        <h3>Empfohlene Variante</h3>
                        <table>
                            <tr><th>Variante</th><td>{passende_variante.name}</td></tr>
                            <tr><th>Beschreibung</th><td>{passende_variante.beschreibung}</td></tr>
                            <tr><th colspan="2" style="text-align:center;">Komponenten & Preise</th></tr>
                            {varianten_details_html}
                        </table>

                        <h3>Ihre Angaben zur Bestandsaufnahme</h3>
                        <table>
                            {bestandsaufnahme_html}
                        </table>

                        <p>Sie können Ihr Projekt unter folgendem Link im Admin-Bereich einsehen:<br>
                        <a href="{admin_url}">{admin_url}</a></p>

                        <p>Mit freundlichen Grüßen,<br>Ihr Planungstool</p>
                    </body>
                </html>
                """

                plain_text_message = f"Vielen Dank. Empfohlene Variante: {passende_variante.name}"
                msg = EmailMultiAlternatives(subject, plain_text_message, from_email, recipient_list)
                msg.attach_alternative(html_content, "text/html")
                try:
                    msg.send()
                except Exception as e:
                    print(f"Email konnte nicht gesendet werden: {e}")

                return redirect('sportplatzApp:danke_seite', projekt_id=neues_projekt.id)
            else:
                return redirect('sportplatzApp:keine_variante_gefunden')
    else:
        form = ProjektForm()

    return render(request, 'sportplatzApp/projekt_anlegen.html', {'form': form})


def danke_seite(request, projekt_id):
    projekt = get_object_or_404(Projekt, pk=projekt_id)
    context = {'projekt': projekt}
    return render(request, 'sportplatzApp/danke.html', context)


def keine_variante_gefunden(request):
    return render(request, 'sportplatzApp/keine_variante_gefunden.html')
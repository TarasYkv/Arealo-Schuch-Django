# VOLLSTÄNDIGER CODE FÜR: pdf_sucher/views.py

import fitz  # PyMuPDF
import openai
import json
import os
import uuid
from django.conf import settings
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from django.http import Http404, HttpResponse, FileResponse


def text_in_chunks_generieren(text_seiten, chunk_groesse=5, ueberlappung=1):
    for i in range(0, len(text_seiten), chunk_groesse - ueberlappung):
        yield text_seiten[i:i + chunk_groesse]


def pdf_suche(request):
    # HINWEIS: Diese Zeile ist nicht mehr nötig, da der API-Schlüssel
    # direkt bei der Client-Erstellung übergeben wird.
    # openai.api_key = settings.OPENAI_API_KEY

    context = {
        'ergebnisse': [],
        'error_message': None,
        'pdf_filename': None,
        'suchanfrage': '',
        'suggested_keywords': [],
        'seite_von': '',
        'seite_bis': '',
        'step': 'initial'
    }

    if request.method == 'POST':
        step = request.POST.get('step')

        suchanfrage = request.POST.get('suchanfrage', '')
        seite_von_str = request.POST.get('seite_von', '')
        seite_bis_str = request.POST.get('seite_bis', '')

        context['suchanfrage'] = suchanfrage
        context['seite_von'] = seite_von_str
        context['seite_bis'] = seite_bis_str

        if step == 'get_keywords':
            try:
                if 'pdf_datei' not in request.FILES:
                    context['error_message'] = "Bitte wählen Sie eine PDF-Datei aus."
                    return render(request, 'pdf_sucher/suche.html', context)

                pdf_datei = request.FILES['pdf_datei']
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'pdf_uploads'))
                dateiname = f"{uuid.uuid4()}.pdf"
                pdf_filename = fs.save(dateiname, pdf_datei)
                context['pdf_filename'] = pdf_filename
                gespeicherte_pdf_pfad = fs.path(pdf_filename)

                with fitz.open(gespeicherte_pdf_pfad) as doc:
                    kontext_text = "".join(doc[i].get_text("text") for i in range(min(5, len(doc))))

                system_prompt = (
                    "Du bist ein Experte für Beleuchtungstechnik. Ein Benutzer hat eine Suchanfrage für eine technische Ausschreibung. "
                    "Schlage 5 bis 7 relevante, verwandte technische Suchbegriffe oder Synonyme vor. "
                    "Antworte NUR mit einem validen JSON-Objekt. Das Objekt muss einen einzigen Schlüssel namens 'keywords' haben, der eine Liste (Array) von Strings enthält. "
                    "Beispiel: {\"keywords\": [\"Schutzart IP65\", \"EN 12464-1\", \"DALI-Schnittstelle\"]}"
                )

                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",
                         "content": f"Auszug aus der Ausschreibung: '{kontext_text[:2000]}'\n\nUrsprüngliche Suchanfrage: '{suchanfrage}'"}
                    ]
                )
                antwort_text = response.choices[0].message.content
                antwort_objekt = json.loads(antwort_text)
                context['suggested_keywords'] = antwort_objekt.get('keywords', [])
                context['step'] = 'select_keywords'

            except Exception as e:
                context['error_message'] = f"Fehler bei der Generierung der Suchbegriffe: {e}"
                context['step'] = 'initial'

        elif step == 'final_search':
            pdf_filename = request.POST.get('pdf_filename', '')
            selected_keywords = request.POST.getlist('selected_keywords')

            context['pdf_filename'] = pdf_filename
            context['step'] = 'results'
            final_query = suchanfrage + " " + " ".join(selected_keywords)

            try:
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'pdf_uploads'))
                gespeicherte_pdf_pfad = fs.path(pdf_filename)
                alle_seiten = []
                with fitz.open(gespeicherte_pdf_pfad) as doc:
                    for seite_num, seite in enumerate(doc):
                        alle_seiten.append((seite_num + 1, seite.get_text("text")))

                seite_von = int(seite_von_str) if seite_von_str.isdigit() else 1
                seite_bis = int(seite_bis_str) if seite_bis_str.isdigit() else len(alle_seiten)

                zu_durchsuchende_seiten = [s for s in alle_seiten if seite_von <= s[0] <= seite_bis and s[1].strip()]

                if not zu_durchsuchende_seiten:
                    context['error_message'] = "Der angegebene Seitenbereich ist ungültig oder enthält keinen Text."
                else:
                    for chunk in text_in_chunks_generieren(zu_durchsuchende_seiten):
                        chunk_text = "\n\n".join([f"--- SEITE {s_num} ---\n{s_text}" for s_num, s_text in chunk])

                        system_prompt_final = (
                            "Du bist ein erfahrener Elektroplaner. Deine Aufgabe ist es, technische Ausschreibungen zu analysieren. "
                            "Finde die exakten Textstellen, die technische Spezifikationen, Normen, oder Produktanforderungen enthalten. "
                            "Antworte NUR mit einem validen JSON-Objekt mit einem Schlüssel 'ergebnisse', der eine Liste von Objekten enthält. "
                            "Jedes Objekt muss die Schlüssel 'seitenzahl' (Zahl) und 'textstelle' (exaktes Zitat) haben. "
                            "Wenn du nichts findest, gib eine leere Liste zurück: {\"ergebnisse\": []}"
                        )

                        try:
                            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                            response = client.chat.completions.create(
                                model="gpt-3.5-turbo-1106",
                                response_format={"type": "json_object"},
                                messages=[
                                    {"role": "system", "content": system_prompt_final},
                                    {"role": "user",
                                     "content": f"Textabschnitt: '{chunk_text}'\n\nSuchanfrage: '{final_query}'"}
                                ]
                            )
                            antwort_objekt = json.loads(response.choices[0].message.content)
                            chunk_ergebnisse = antwort_objekt.get('ergebnisse', [])
                            if isinstance(chunk_ergebnisse, list):
                                context['ergebnisse'].extend(chunk_ergebnisse)
                        except Exception as e:
                            print(f"Fehler bei finaler Chunk-Verarbeitung: {e}")
                            continue
            except Exception as e:
                context['error_message'] = f"Fehler bei der finalen Suche: {e}"

    return render(request, 'pdf_sucher/suche.html', context)


def view_pdf(request, filename):
    """
    Zeigt die hochgeladene PDF-Datei sicher im Browser an.
    """
    file_path = os.path.join(settings.MEDIA_ROOT, 'pdf_uploads', filename)

    # KORREKTUR: Sicherheitsüberprüfung hinzugefügt
    if not os.path.normpath(file_path).startswith(os.path.normpath(os.path.join(settings.MEDIA_ROOT, 'pdf_uploads'))):
        raise Http404("Ungültiger Dateipfad")

    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')

    raise Http404("PDF nicht gefunden")


def pdf_page_preview(request, filename, page_num):
    """
    Rendert eine spezifische Seite einer PDF als PNG-Bild und gibt es zurück.
    """
    file_path = os.path.join(settings.MEDIA_ROOT, 'pdf_uploads', filename)

    # KORREKTUR: Sicherheitsüberprüfung hinzugefügt
    if not os.path.normpath(file_path).startswith(os.path.normpath(os.path.join(settings.MEDIA_ROOT, 'pdf_uploads'))):
        raise Http404("Ungültiger Dateipfad")

    try:
        doc = fitz.open(file_path)
        if 0 <= page_num - 1 < doc.page_count:
            page = doc.load_page(page_num - 1)
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            doc.close()
            return HttpResponse(img_data, content_type="image/png")
        else:
            doc.close()
            raise Http404("Seitenzahl außerhalb des gültigen Bereichs")
    except FileNotFoundError:
        raise Http404("PDF nicht gefunden")
    except Exception as e:
        print(f"Fehler beim Rendern der PDF-Seite: {e}")
        raise Http404("Seite konnte nicht gerendert werden")
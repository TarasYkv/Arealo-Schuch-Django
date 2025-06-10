# Kompletter Inhalt für: pdf_sucher/views.py

import fitz  # PyMuPDF
import openai
import json
from django.conf import settings
from django.shortcuts import render


def text_in_chunks_generieren(text_seiten, chunk_groesse=3, ueberlappung=1):
    """
    Diese Hilfsfunktion teilt die Seiten des Dokuments in überlappende "Chunks".
    """
    for i in range(0, len(text_seiten), chunk_groesse - ueberlappung):
        yield text_seiten[i:i + chunk_groesse]


def pdf_suche(request):
    openai.api_key = settings.OPENAI_API_KEY

    ergebnisse = []
    error_message = None

    if request.method == 'POST' and request.FILES.get('pdf_datei'):
        pdf_datei = request.FILES['pdf_datei']
        suchanfrage = request.POST.get('suchanfrage', '')

        try:
            # 1. Text aus der PDF-Datei extrahieren
            text_pro_seite = []
            with fitz.open(stream=pdf_datei.read(), filetype="pdf") as doc:
                for seite_num, seite in enumerate(doc):
                    text = seite.get_text("text")
                    if text.strip():
                        text_pro_seite.append((seite_num + 1, text))

            if text_pro_seite and suchanfrage:
                # 2. Schleife durch die "Chunks" und API-Aufrufe
                for chunk in text_in_chunks_generieren(text_pro_seite):
                    chunk_text = "\n\n".join([f"--- SEITE {seite_num} ---\n{text}" for seite_num, text in chunk])

                    # NEUER, TECHNISCHER PROMPT
                    system_prompt = (
                        "Du bist ein erfahrener Elektroplaner und Ingenieur für Beleuchtungstechnik. Deine Aufgabe ist es, technische Ausschreibungen (LV-Texte) in PDF-Form zu analysieren. "
                        "Analysiere den folgenden Textabschnitt aus einer Ausschreibung. "
                        "Der Benutzer wird eine technische Frage oder nach Schlüsselwörtern suchen. "
                        "Finde die exakten, relevanten Textstellen, die technische Spezifikationen, Normen, Produktanforderungen oder Mengenangaben enthalten. "
                        "Ignoriere Füllwörter und allgemeine Phrasen. Konzentriere dich auf die harten Fakten. "
                        "Antworte NUR mit einem validen JSON-Objekt. Das Objekt muss einen einzigen Schlüssel "
                        "namens 'ergebnisse' haben, der eine Liste (Array) von Objekten enthält. Jedes Objekt in der Liste muss die Schlüssel "
                        "'seitenzahl' (als Zahl) und 'textstelle' (als String mit dem exakten technischen Zitat) haben. Entnimm die Seitenzahl aus den '--- SEITE X ---' Markern. "
                        "Wenn du nichts findest, gib eine leere Liste für 'ergebnisse' zurück: {\"ergebnisse\": []}"
                    )

                    try:
                        # API-AUFRUF MIT JSON-MODUS
                        response = openai.chat.completions.create(
                            model="gpt-3.5-turbo-1106",  # Dieses Modell unterstützt den JSON-Modus sehr gut
                            response_format={"type": "json_object"},
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user",
                                 "content": f"Textabschnitt: '{chunk_text}'\n\nSuchanfrage: '{suchanfrage}'"}
                            ]
                        )
                        antwort_text = response.choices[0].message.content

                        antwort_objekt = json.loads(antwort_text)
                        chunk_ergebnisse = antwort_objekt.get('ergebnisse', [])

                        if isinstance(chunk_ergebnisse, list):
                            ergebnisse.extend(chunk_ergebnisse)

                    except (json.JSONDecodeError, IndexError, TypeError) as e:
                        print(f"Fehler bei der Verarbeitung eines Chunks: {e}")
                        continue

        except Exception as e:
            error_message = f"Ein Fehler ist aufgetreten: {e}"

    return render(request, 'pdf_sucher/suche.html', {
        'ergebnisse': ergebnisse,
        'error_message': error_message
    })
